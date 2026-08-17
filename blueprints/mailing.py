"""Blueprint mailing : composition et envoi des campagnes, file d'attente,
historique, demandes de diffusion (IMAP), preview et test SMTP.

Endpoints : mailing.compose, mailing.history, mailing.queue_retry,
mailing.history_archive/unarchive/delete, mailing.submissions,
mailing.submission_use/archive/attachment, mailing.preview, mailing.send,
mailing.confirm, mailing.add_to_queue, mailing.queue, mailing.process,
mailing.submission_preview, mailing.test_connection.
"""
import re
import unicodedata

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, send_from_directory)
from flask_login import login_required, current_user

from models import Contact, Liste, PreferenceForm, MailCampaign, MailQueueItem, ContactSend, db, utcnow
from config import Config
from helpers import admin_required, listes_sorted

bp = Blueprint('mailing', __name__)


# Bloc de signature en pied de mail : marqué (data-mail-sig) pour pouvoir le
# retirer proprement au ré-affichage / avant de le ré-appliquer (jamais d'accumulation).
# Matche aussi l'ancien bloc (sans marqueur) des campagnes créées avant ce correctif.
_SIG_RE = re.compile(
    r'\s*<p[^>]*(?:data-mail-sig="1"|color:#8a8a8a;font-size:12px)[^>]*>.*?</p>',
    re.DOTALL)


def _strip_signature(body):
    """Retire tout bloc de signature déjà présent dans le corps (HTML)."""
    if not body:
        return body
    return _SIG_RE.sub('', body).rstrip()


def _norm_name(s):
    """Normalise un nom de liste pour le matching (minuscule, sans accents, espaces compactés)."""
    s = unicodedata.normalize('NFKD', (s or '').strip().lower()).encode('ascii', 'ignore').decode()
    return ' '.join(s.split())


def _lists_by_norm():
    """{nom_normalisé: Liste} des listes actives (pour matcher un préfixe de sujet)."""
    return {_norm_name(l.nom): l for l in Liste.query.filter_by(is_archived=False).all()}


def _match_subject_lists(raw, by_norm):
    """Applique la convention « liste1,liste2: sujet réel » à un sujet brut.

    `by_norm` = map {nom_normalisé: Liste}. Renvoie (sujet_nettoyé, [Liste reconnues],
    [noms non reconnus]). Garde-fou : si AUCUN token ne correspond à une liste connue,
    on considère qu'il n'y avait pas de préfixe (un sujet peut contenir un « : »)."""
    import imap_submissions
    tokens, after_colon, base = imap_submissions.split_subject_lists(raw)
    if not tokens:
        return base, [], []
    matched, unknown = [], []
    for t in tokens:
        l = by_norm.get(_norm_name(t))
        matched.append(l) if l else unknown.append(t)
    if matched:
        return after_colon, matched, unknown
    return base, [], []


def _parse_submission_subject(raw):
    """(sujet_nettoyé, [liste_ids reconnus], [noms non reconnus]) — un « mailing: » de
    tête est toléré/retiré."""
    clean, matched, unknown = _match_subject_lists(raw, _lists_by_norm())
    return clean, [l.id for l in matched], unknown


def _sign_body(body, mail_format, sign, signature):
    """Retire toute signature existante puis, si « Signer cette diffusion » est
    coché, ajoute UNE signature en pied de mail. Idempotent (0 ou 1 signature)."""
    body = _strip_signature(body) if mail_format == 'html' else body
    if not (sign and signature):
        return body
    if mail_format == 'html':
        return (body + '<p data-mail-sig="1" style="margin-top:24px;color:#8a8a8a;'
                f'font-size:12px;">— {signature}</p>')
    return body + f'\n\n— {signature}'


def _recipients(liste_ids, use_selection=False):
    """Union DÉDOUBLONNÉE (par id) des contacts actifs (non supprimés, non désabonnés)
    des listes données ET — si `use_selection` — de la « sélection courante » de
    l'utilisateur. Un contact présent dans plusieurs sources n'apparaît qu'une fois.
    Ordre de première apparition (listes d'abord, puis sélection)."""
    seen = {}
    for lid in liste_ids:
        liste = Liste.query.get(lid)
        if not liste:
            continue
        for c in liste.active_contacts:
            if not c.is_unsubscribed and c.id not in seen:
                seen[c.id] = c
    if use_selection:
        from contact_set import ContactSet
        for c in ContactSet.for_user(current_user.id).contacts().all():
            if not c.is_unsubscribed and c.id not in seen:
                seen[c.id] = c
    return list(seen.values())


def _recipients_for_lists(liste_ids):
    """Compat : destinataires des seules listes (sans la sélection courante)."""
    return _recipients(liste_ids, use_selection=False)


@bp.route('/mailing/recipients-count', methods=['POST'])
@login_required
def recipients_count():
    """Compteur live pour le rail Destinataires : total dédoublonné des listes cochées
    (+ sélection courante si l'entrée « ★ Sélection courante » est cochée)."""
    liste_ids = request.form.getlist('liste_ids', type=int)
    use_selection = request.form.get('use_selection') == '1'
    n = len(_recipients(liste_ids, use_selection))
    return jsonify({'count': n, 'lists': len(liste_ids) + (1 if use_selection else 0)})


@bp.route('/mailing')
@login_required
def compose():
    # Rail Destinataires : actives seulement (cohérent avec Contacts/Listes), triées
    # lisiblement (casse/accents-insensible) via le helper partagé.
    listes = listes_sorted(is_archived=False)
    smtp_configured = bool(Config.SMTP_HOST and Config.SMTP_USER)

    # Pré-remplissage depuis l'historique (réutilisation par campaign_id)
    prefill = {'name': '', 'subject': '', 'body': '', 'format': 'text', 'liste_ids': []}
    campaign_attachments = []   # PJ déjà enregistrées (réutilisation / retour édition)
    from_campaign_id = None
    sign_checked = bool(current_user.moderation_signature)
    # Entrée « ★ Sélection courante » pré-cochée : deep-link depuis /selection, ou
    # réutilisation d'une campagne qui ciblait la sélection.
    use_selection_checked = request.args.get('from_selection') == '1'
    from_campaign = request.args.get('from_campaign')
    if from_campaign:
        from mailer import MailQueue
        tpl = MailQueue().get_campaign_template(from_campaign)
        if tpl:
            prefill = {
                'name': tpl.get('name', ''),
                'subject': tpl.get('subject', ''),
                'body': tpl.get('body', ''),
                'format': tpl.get('format', 'text'),
                'liste_ids': tpl.get('liste_ids') or ([tpl['liste_id']] if tpl.get('liste_id') else []),
            }
            import os as _os
            campaign_attachments = [_os.path.basename(p) for p in (tpl.get('attachments') or [])]
            from_campaign_id = from_campaign
            use_selection_checked = use_selection_checked or bool(tpl.get('use_selection'))
            # La signature est un pied de mail, pas du contenu éditable : on la
            # retire du corps affiché (et on reflète l'état « signé »).
            sign_checked = bool(_SIG_RE.search(prefill['body']))
            prefill['body'] = _strip_signature(prefill['body'])

    # Pré-remplissage depuis une demande de diffusion (boîte IMAP)
    # Stocké sur disque (et non en session) car le corps peut contenir des
    # images encodées en base64, trop volumineuses pour un cookie de session.
    submission_attachments = []
    submission_id = None
    submission_unknown_lists = []
    from_submission = request.args.get('from_submission')
    if from_submission:
        import json
        from pathlib import Path
        prefill_path = Path(f'data/attachments/submission_{from_submission}/_prefill.json')
        if prefill_path.exists():
            data = json.loads(prefill_path.read_text(encoding='utf-8'))
            prefill = {
                'subject': data.get('subject', ''),
                'body': data.get('body', ''),
                'format': data.get('format', 'text'),
                # Listes cibles déduites du sujet « liste1,liste2: … » → pré-cochées (modifiables)
                'liste_ids': data.get('liste_ids', []),
            }
            submission_attachments = data.get('attachments', [])
            submission_id = from_submission
            submission_unknown_lists = data.get('unknown_lists', [])

    forms = (PreferenceForm.query
             .filter_by(is_active=True, is_archived=False)
             .order_by(PreferenceForm.nom).all())
    return render_template('mailing.html', listes=listes, smtp_configured=smtp_configured, prefill=prefill,
                           submission_attachments=submission_attachments, submission_id=submission_id,
                           submission_unknown_lists=submission_unknown_lists,
                           campaign_attachments=campaign_attachments, from_campaign_id=from_campaign_id,
                           sign_checked=sign_checked, use_selection_checked=use_selection_checked,
                           forms=forms, base_url=Config.BASE_URL,
                           signature=current_user.moderation_signature or '')


@bp.route('/mailing/history')
@login_required
def history():
    from mailer import MailQueue
    queue = MailQueue()
    campaigns = queue.get_campaigns_list()
    archived = queue.get_archived_campaigns_list()
    drafts = queue.get_drafts_list()

    bounced_emails = {c.email for c in Contact.query.filter_by(has_bounced=True).all()}
    for c in campaigns + archived:
        c['stats']['bounced'] = len(c['sent_emails'] & bounced_emails)

    return render_template('mailing_history.html', campaigns=campaigns,
                           archived=archived, drafts=drafts)


@bp.route('/mailing/queue/retry/<campaign_id>', methods=['POST'])
@login_required
def queue_retry(campaign_id):
    from mailer import MailQueue
    queue = MailQueue()
    queue.reset_errors(campaign_id)
    flash('Erreurs remises en attente. Vous pouvez relancer l\'envoi.', 'success')
    return redirect(url_for('mailing.queue', campaign=campaign_id))


@bp.route('/mailing/history/archive/<campaign_id>', methods=['POST'])
@login_required
def history_archive(campaign_id):
    from mailer import MailQueue
    queue = MailQueue()
    queue.archive_campaign(campaign_id)
    flash('Campagne archivée.', 'success')
    return redirect(url_for('mailing.history'))


@bp.route('/mailing/history/unarchive/<campaign_id>', methods=['POST'])
@login_required
def history_unarchive(campaign_id):
    from mailer import MailQueue
    queue = MailQueue()
    queue.unarchive_campaign(campaign_id)
    flash('Campagne restaurée.', 'success')
    return redirect(url_for('mailing.history'))


@bp.route('/mailing/history/delete/<campaign_id>', methods=['POST'])
@login_required
@admin_required
def history_delete(campaign_id):
    from mailer import MailQueue
    queue = MailQueue()
    queue.delete_campaign(campaign_id)
    flash('Campagne supprimée.', 'success')
    return redirect(url_for('mailing.history'))


@bp.route('/mailing/submissions')
@login_required
def submissions():
    """Liste les demandes de diffusion reçues sur la boîte IMAP dédiée"""
    imap_configured = bool(Config.IMAP_HOST and Config.IMAP_USER)
    show_archived = request.args.get('archived') == '1'
    submissions = []
    archived = []
    error = None

    if imap_configured:
        import imap_submissions
        try:
            submissions = imap_submissions.fetch_submissions(Config)
            if show_archived:
                archived = imap_submissions.fetch_submissions(Config, folder=Config.IMAP_PROCESSED_FOLDER)
            # Enrichir l'affichage : sujet nettoyé + listes cibles déduites du sujet
            # (« liste1,liste2: sujet »), pour voir le routage sans ouvrir la demande.
            by_norm = _lists_by_norm()
            for s in submissions + archived:
                clean, matched, unknown = _match_subject_lists(s['subject'], by_norm)
                s['clean_subject'] = clean
                s['lists'] = [l.nom for l in matched]
                s['unknown_lists'] = unknown
        except Exception as e:
            error = str(e)

    return render_template('mailing_submissions.html', submissions=submissions,
                           archived=archived, show_archived=show_archived,
                           imap_configured=imap_configured, error=error)


@bp.route('/mailing/submissions/<uid>/use', methods=['POST'])
@login_required
def submission_use(uid):
    """Pré-remplit le formulaire mailing depuis une demande.

    Le message n'est marqué comme traité que lorsque le mailing est
    effectivement mis en file d'envoi (cf. mailing.add_to_queue), afin
    qu'une demande abandonnée en cours de route reste visible."""
    import imap_submissions
    from werkzeug.utils import secure_filename
    from pathlib import Path

    try:
        sub = imap_submissions.get_submission(Config, uid)
        if not sub:
            flash('Message introuvable (déjà traité ?)', 'error')
            return redirect(url_for('mailing.submissions'))

        # Sauvegarder les pièces jointes sur disque
        import json
        attach_dir = Path(f'data/attachments/submission_{uid}')
        attach_dir.mkdir(parents=True, exist_ok=True)
        saved_attachments = []
        for a in sub['attachments']:
            filename = secure_filename(a['filename'])
            if filename:
                (attach_dir / filename).write_bytes(a['payload'])
                saved_attachments.append(filename)

        body = sub['body_html'] or sub['body_text']
        fmt = 'html' if sub['body_html'] else 'text'

        # Sujet « liste1,liste2: vrai sujet » → listes cibles pré-sélectionnées + sujet nettoyé
        clean_subject, liste_ids, unknown_lists = _parse_submission_subject(sub['subject'])

        # Pré-remplissage stocké sur disque (peut être volumineux : images
        # encodées en base64), pas en session
        prefill_data = {
            'subject': clean_subject,
            'body': body,
            'format': fmt,
            'attachments': saved_attachments,
            'liste_ids': liste_ids,
            'unknown_lists': unknown_lists,
        }
        (attach_dir / '_prefill.json').write_text(json.dumps(prefill_data), encoding='utf-8')

        return redirect(url_for('mailing.compose', from_submission=uid))
    except Exception as e:
        flash(f'Erreur lors de la lecture du message : {e}', 'error')
        return redirect(url_for('mailing.submissions'))


@bp.route('/mailing/submissions/<uid>/preview')
@login_required
def submission_preview(uid):
    """Aperçu (corps + PJ) d'UNE demande, chargé à la demande au clic « Voir » —
    évite de rapatrier tous les corps dans la liste. `?archived=1` = dossier traité."""
    if not (Config.IMAP_HOST and Config.IMAP_USER):
        return '<p class="text-muted">Boîte non configurée.</p>'
    import imap_submissions
    folder = Config.IMAP_PROCESSED_FOLDER if request.args.get('archived') == '1' else None
    try:
        sub = imap_submissions.get_submission(Config, uid, folder=folder)
    except Exception:
        return '<p class="text-muted">Erreur de chargement du message.</p>'
    if not sub:
        return '<p class="text-muted">Message introuvable (déjà traité ?).</p>'
    return render_template('_submission_preview.html', s=sub)


@bp.route('/mailing/submissions/<uid>/archive', methods=['POST'])
@login_required
def submission_archive(uid):
    """Archive une demande sans l'utiliser"""
    import imap_submissions
    try:
        imap_submissions.mark_processed(Config, uid)
        flash('Demande archivée.', 'success')
    except Exception as e:
        flash(f'Erreur : {e}', 'error')
    return redirect(url_for('mailing.submissions'))


@bp.route('/mailing/submission-attachment/<submission_id>/<filename>')
@login_required
def submission_attachment(submission_id, filename):
    """Affiche (images/PDF, dans l'onglet) ou télécharge une pièce jointe de demande.

    Sécurité : on ne sert INLINE que des types sûrs à afficher. Un SVG ou un HTML
    servi inline depuis notre origine pourrait exécuter du script (XSS) avec la
    session de l'utilisateur connecté — ceux-là restent en téléchargement forcé.
    nosniff empêche le navigateur de re-deviner un type exécutable."""
    from pathlib import Path
    import mimetypes
    attach_dir = Path(f'data/attachments/submission_{submission_id}').absolute()
    mime, _ = mimetypes.guess_type(filename)
    inline_ok = mime in {'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'application/pdf'}
    resp = send_from_directory(attach_dir, filename, as_attachment=not inline_ok)
    resp.headers['X-Content-Type-Options'] = 'nosniff'
    return resp


@bp.route('/mailing/preview', methods=['POST'])
@login_required
def preview():
    """Prévisualisation du mail avec un contact de la liste"""
    liste_ids = request.form.getlist('liste_ids', type=int)
    use_selection = request.form.get('use_selection') == '1'
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    mail_format = request.form.get('format', 'text')
    include_unsubscribe = request.form.get('include_unsubscribe') == 'on'
    contact_index = request.form.get('contact_index', 0, type=int)
    body = _sign_body(body, mail_format, request.form.get('sign') == 'on',
                      current_user.moderation_signature)

    if not liste_ids and not use_selection:
        return jsonify({'error': 'Sélectionnez au moins une liste ou la sélection courante'}), 400

    # Aperçu sur l'union dédoublonnée des listes cochées (+ sélection si cochée)
    recipients = _recipients(liste_ids, use_selection)
    if not recipients:
        return jsonify({'error': 'Aucun contact actif dans la sélection'}), 400

    # Sélectionner le contact par index (borné)
    total = len(recipients)
    contact_index = max(0, min(contact_index, total - 1))
    contact = recipients[contact_index]
    contact_dict = contact.to_dict()

    from mailer import EmailTemplate
    unsub_url = f"{Config.BASE_URL}/unsubscribe/{contact.uid}" if include_unsubscribe else None
    tpl = EmailTemplate(
        subject=subject,
        body_text=body if mail_format == 'text' else '',
        body_html=body if mail_format == 'html' else None,
    )
    preview_subject, preview_body_text, preview_body_html = tpl.render(contact_dict, unsubscribe_url=unsub_url)
    preview_body = preview_body_html if mail_format == 'html' else preview_body_text

    # Aperçu : désactiver les liens pour éviter qu'en prévisualisant on clique
    # sur un lien live (ex. formulaire de préférences) et qu'on modifie de vraies
    # données. Les liens restent fonctionnels dans l'email réellement envoyé.
    if mail_format == 'html' and preview_body:
        import re as _re
        preview_body = _re.sub(r'<a\b', '<a onclick="return false;" style="cursor:default;"',
                               preview_body, flags=_re.IGNORECASE)

    return jsonify({
        'subject': preview_subject,
        'body': preview_body,
        'contact': f"{contact.prenom} {contact.nom} <{contact.email}>",
        'index': contact_index,
        'total': total
    })


# Variables simples {prenom} — PAS les conditionnelles {champ:si:sinon} (qui
# contiennent un « : »), qu'on ne doit pas altérer.
_SIMPLE_VAR_RE = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')


def _highlight_vars(body):
    """Entoure chaque variable simple d'un <mark> AVANT la substitution : la
    valeur substituée ressort donc surlignée dans l'aperçu."""
    return _SIMPLE_VAR_RE.sub(lambda m: f'<mark class="var-hl">{m.group(0)}</mark>', body or '')


def _render_campaign_for(tpl, contact, highlight=False):
    """Rend (sujet, corps) d'une campagne pour un contact donné, comme il sera reçu."""
    from mailer import EmailTemplate
    mail_format = tpl.get('format', 'html')
    body = tpl.get('body', '')
    if highlight and mail_format == 'html':
        body = _highlight_vars(body)
    unsub_url = (f"{Config.BASE_URL}/unsubscribe/{contact.uid}"
                 if tpl.get('include_unsubscribe') else None)
    et = EmailTemplate(subject=tpl.get('subject', ''),
                       body_text=body if mail_format == 'text' else '',
                       body_html=body if mail_format == 'html' else None)
    subject, body_text, body_html = et.render(contact.to_dict(), unsubscribe_url=unsub_url)
    return subject, (body_html if mail_format == 'html' else body_text), (mail_format == 'html')


def _campaign_liste_ids(tpl):
    return tpl.get('liste_ids') or ([tpl['liste_id']] if tpl.get('liste_id') else [])


@bp.route('/mailing/apercu')
@login_required
def apercu():
    """Étape 2 « Aperçu » : le mail tel qu'il sera reçu, contact par contact."""
    from mailer import MailQueue
    campaign_id = request.args.get('campaign')
    if not campaign_id:
        return redirect(url_for('mailing.compose'))
    tpl = MailQueue().get_campaign_template(campaign_id)
    if not tpl:
        flash('Campagne introuvable', 'error')
        return redirect(url_for('mailing.compose'))

    liste_ids = _campaign_liste_ids(tpl)
    listes = Liste.query.filter(Liste.id.in_(liste_ids)).all()
    recipients = _recipients_for_lists(liste_ids)
    if not recipients:
        flash('Aucun destinataire actif dans la sélection.', 'error')
        return redirect(url_for('mailing.compose', from_campaign=campaign_id))

    total = len(recipients)
    index = max(0, min(request.args.get('i', 0, type=int), total - 1))
    contact = recipients[index]
    highlight = request.args.get('hl', '1') != '0'

    subject, body, is_html = _render_campaign_for(tpl, contact, highlight=highlight)
    # Liens neutralisés dans l'aperçu (ne pas déclencher un vrai formulaire).
    if is_html and body:
        body = re.sub(r'<a\b', '<a onclick="return false;" style="cursor:default;"',
                      body, flags=re.IGNORECASE)

    return render_template('mailing_apercu.html',
                           campaign_id=campaign_id, template=tpl, listes=listes,
                           contact=contact, index=index, total=total,
                           subject=subject, body=body, is_html=is_html,
                           highlight=highlight,
                           sender_name=Config.SMTP_SENDER_NAME or Config.SMTP_SENDER_EMAIL,
                           sender_email=Config.SMTP_SENDER_EMAIL,
                           test_email=getattr(current_user, 'email', '') or '')


@bp.route('/mailing/send-test', methods=['POST'])
@login_required
def send_test():
    """Envoie UN exemplaire du mail à une adresse de test (aperçu réel en boîte)."""
    from mailer import Mailer, MailQueue
    campaign_id = request.form.get('campaign_id')
    to_email = (request.form.get('test_email') or '').strip()
    index = request.form.get('i', 0, type=int)
    back = url_for('mailing.apercu', campaign=campaign_id, i=index)

    if not to_email:
        flash('Indiquez une adresse pour le test.', 'error')
        return redirect(back)
    if not Config.SMTP_HOST:
        flash('SMTP non configuré : impossible d\'envoyer un test.', 'error')
        return redirect(back)

    tpl = MailQueue().get_campaign_template(campaign_id)
    recipients = _recipients_for_lists(_campaign_liste_ids(tpl)) if tpl else []
    if not tpl or not recipients:
        flash('Campagne ou destinataires introuvables.', 'error')
        return redirect(back)

    contact = recipients[max(0, min(index, len(recipients) - 1))]
    subject, body, is_html = _render_campaign_for(tpl, contact)
    # Marqueur de TEST : on ajoute ?test=1 aux liens de formulaire (/p/<token>/<uid>)
    # UNIQUEMENT dans l'exemplaire de test → la soumission sera taguée is_test et
    # exclue partout (verrou, compteurs, export). Les campagnes réelles ne sont pas touchées.
    import re as _re
    body = _re.sub(r"(/p/[^\"'\s?<>]+)(?!\?)", r"\1?test=1", body or '')
    mailer = Mailer(Config.SMTP_HOST, Config.SMTP_PORT, Config.SMTP_USER,
                    Config.SMTP_PASSWORD, Config.SMTP_SENDER_EMAIL,
                    Config.SMTP_SENDER_NAME, Config.SMTP_USE_TLS)
    try:
        ok = mailer.send_single(to_email, f'[TEST] {subject}',
                                body if not is_html else '',
                                body if is_html else None,
                                attachments=tpl.get('attachments'))
        flash(f'Email de test envoyé à {to_email}.' if ok
              else f'Échec de l\'envoi du test à {to_email}.',
              'success' if ok else 'error')
    except Exception as e:
        flash(f'Erreur lors de l\'envoi du test : {e}', 'error')
    return redirect(back)


def _persist_campaign_from_form(reuse_id=None):
    """Valide le formulaire du Composer et enregistre la campagne (template + PJ).

    Partagé par « Continuer vers l'aperçu » et « Enregistrer le brouillon ».
    Si `reuse_id` est fourni (on revient éditer une campagne existante), on MET À
    JOUR cette campagne au lieu d'en créer une nouvelle — sinon chaque aller-retour
    laissait derrière lui une campagne orpheline.

    Retourne (campaign_id, None) en cas de succès, (None, message) sinon.
    """
    from mailer import MailQueue
    from datetime import datetime

    liste_ids = request.form.getlist('liste_ids', type=int)
    use_selection = request.form.get('use_selection') == '1'
    name = (request.form.get('name') or '').strip() or None
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    mail_format = request.form.get('format', 'text')

    if not ((liste_ids or use_selection) and subject and body):
        return None, 'Sélectionnez au moins une liste (ou la sélection courante), un sujet et un message.'

    body = _sign_body(body, mail_format, request.form.get('sign') == 'on',
                      current_user.moderation_signature)

    if not Config.SMTP_HOST:
        return None, 'SMTP non configuré'

    listes = Liste.query.filter(Liste.id.in_(liste_ids)).all()
    if liste_ids and not listes:
        return None, 'Liste(s) introuvable(s)'

    include_unsubscribe = request.form.get('include_unsubscribe') == 'on'

    # Union DÉDOUBLONNÉE des contacts actifs (désabonnés exclus) : listes + sélection courante
    recipients = _recipients(liste_ids, use_selection)
    all_active_ids = {c.id for lst in listes for c in lst.active_contacts}
    if use_selection:
        from contact_set import ContactSet
        all_active_ids |= {c.id for c in ContactSet.for_user(current_user.id).contacts().all()}
    excluded = len(all_active_ids) - len(recipients)
    if excluded:
        flash(f'{excluded} contact{"s" if excluded > 1 else ""} désabonné{"s" if excluded > 1 else ""} exclu{"s" if excluded > 1 else ""} de l\'envoi', 'info')

    if not recipients:
        return None, 'Aucun contact actif (listes vides ou tous désabonnés).'

    # Détecter les emails partagés par plusieurs contacts
    email_counts = {}
    for c in recipients:
        email_counts[c.email] = email_counts.get(c.email, 0) + 1
    shared = sum(1 for n in email_counts.values() if n > 1)
    if shared:
        flash(f'Attention : {shared} adresse{"s" if shared > 1 else ""} partagée{"s" if shared > 1 else ""} '
              f'par plusieurs contacts. Chaque contact recevra son email personnalisé.', 'warning')

    if reuse_id:
        campaign_id = reuse_id          # on met à jour la campagne en cours d'édition
    else:
        # ID de campagne : nom de la 1re liste (+ « +N » si plusieurs), ou « Sélection »
        # si l'envoi ne cible que la sélection courante.
        id2nom = {lst.id: lst.nom for lst in listes}
        if liste_ids:
            primary = id2nom.get(liste_ids[0], 'Diffusion')
            extra = len(liste_ids) - 1 + (1 if use_selection else 0)
            label = primary if extra == 0 else f"{primary}+{extra}"
        else:
            label = 'Sélection'
        campaign_id = f"{label}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Sauvegarder les pièces jointes sur disque
    from werkzeug.utils import secure_filename
    from pathlib import Path
    import shutil
    attachment_paths = []
    uploaded_files = request.files.getlist('attachments')
    submission_id = request.form.get('submission_id') or None
    # Pièces jointes de la demande explicitement validées par l'utilisateur
    included_submission_attachments = set(request.form.getlist('submission_attachments'))
    # Pièces jointes déjà enregistrées d'une campagne (retour édition / réutilisation)
    kept_attachments = set(request.form.getlist('kept_attachments'))
    from_campaign_id = request.form.get('from_campaign_id') or None
    if (uploaded_files and uploaded_files[0].filename) or included_submission_attachments or kept_attachments:
        attach_dir = Path(f'data/attachments/{campaign_id}')
        attach_dir.mkdir(parents=True, exist_ok=True)
        for f in uploaded_files:
            if f.filename:
                filename = secure_filename(f.filename)
                if filename:
                    filepath = attach_dir / filename
                    f.save(str(filepath))
                    attachment_paths.append(str(filepath))

        # Reprendre les pièces jointes de la demande de diffusion validées par l'utilisateur
        if submission_id and included_submission_attachments:
            submission_dir = Path(f'data/attachments/submission_{submission_id}')
            if submission_dir.is_dir():
                for f in submission_dir.iterdir():
                    if f.is_file() and f.name in included_submission_attachments:
                        dest = attach_dir / f.name
                        shutil.copy(str(f), str(dest))
                        attachment_paths.append(str(dest))

        # Reprendre les PJ déjà enregistrées d'une campagne (retour édition / réutilisation)
        if from_campaign_id and kept_attachments:
            src_dir = Path(f'data/attachments/{from_campaign_id}')
            if src_dir.is_dir():
                for f in src_dir.iterdir():
                    if f.is_file() and f.name in kept_attachments:
                        dest = attach_dir / f.name
                        if str(dest) != str(f):
                            shutil.copy(str(f), str(dest))
                        attachment_paths.append(str(dest))

    # Sauvegarder le template (sans encore peupler la queue)
    MailQueue().set_campaign_template(campaign_id, subject, body, mail_format,
                                      sent_by=current_user.username,
                                      include_unsubscribe=include_unsubscribe,
                                      attachments=attachment_paths or None,
                                      liste_id=(liste_ids[0] if liste_ids else None),
                                      liste_ids=liste_ids, use_selection=use_selection,
                                      submission_id=submission_id, name=name)
    return campaign_id, None


@bp.route('/mailing/send', methods=['POST'])
@login_required
def send():
    """Étape 1 (Composer) -> étape 2 (Aperçu), conformément au process validé."""
    campaign_id, err = _persist_campaign_from_form(request.form.get('from_campaign_id') or None)
    if err:
        flash(err, 'error')
        return redirect(url_for('mailing.compose'))
    return redirect(url_for('mailing.apercu', campaign=campaign_id))


@bp.route('/mailing/save-draft', methods=['POST'])
@login_required
def save_draft():
    """Enregistre le mailing sans quitter le Composer (bouton du mockup)."""
    campaign_id, err = _persist_campaign_from_form(request.form.get('from_campaign_id') or None)
    if err:
        flash(err, 'error')
        return redirect(url_for('mailing.compose'))
    flash('Brouillon enregistré.', 'success')
    return redirect(url_for('mailing.compose', from_campaign=campaign_id))


@bp.route('/mailing/rename', methods=['POST'])
@login_required
def rename():
    """Renomme le mailing depuis le bandeau (nom lisible, distinct de l'objet)."""
    from mailer import MailQueue
    campaign_id = request.form.get('campaign_id')
    new_name = (request.form.get('name') or '').strip()
    camp = db.session.get(MailCampaign, campaign_id) if campaign_id else None
    if camp:
        camp.name = new_name or None
        db.session.commit()
        flash('Mailing renommé.' if new_name else 'Nom du mailing effacé.', 'success')
    return redirect(request.form.get('back') or url_for('mailing.apercu', campaign=campaign_id))


@bp.route('/mailing/confirm')
@login_required
def confirm():
    """Page de confirmation : sélection des contacts avant mise en file"""
    from mailer import MailQueue
    campaign_id = request.args.get('campaign')
    if not campaign_id:
        return redirect(url_for('mailing.compose'))

    queue = MailQueue()
    tpl = queue.get_campaign_template(campaign_id)
    if not tpl:
        flash('Campagne introuvable', 'error')
        return redirect(url_for('mailing.compose'))

    liste_ids = tpl.get('liste_ids') or ([tpl['liste_id']] if tpl.get('liste_id') else [])
    listes = Liste.query.filter(Liste.id.in_(liste_ids)).all()
    recipients = _recipients(liste_ids, tpl.get('use_selection'))

    return render_template('mailing_confirm.html',
                           campaign_id=campaign_id,
                           template=tpl,
                           listes=listes,
                           contacts=recipients)


@bp.route('/mailing/add-to-queue', methods=['POST'])
@login_required
def add_to_queue():
    """Parcours d'envoi (étape Destinataires) : met les contacts sélectionnés en file
    PUIS lance l'envoi IMMÉDIATEMENT. La confirmation DÉCLENCHE l'envoi — fini le piège
    « resté en file, jamais parti ». On arrive en phase Envoi sur un état résultat."""
    from mailer import MailQueue
    campaign_id = request.form.get('campaign_id')
    contact_ids = set(request.form.getlist('contact_ids', type=int))

    if not campaign_id or not contact_ids:
        flash('Aucun contact sélectionné', 'error')
        return redirect(url_for('mailing.compose'))

    queue = MailQueue()
    tpl = queue.get_campaign_template(campaign_id)
    liste_ids = tpl.get('liste_ids') or ([tpl['liste_id']] if tpl.get('liste_id') else [])
    recipients = _recipients(liste_ids, tpl.get('use_selection'))

    selected = [c for c in recipients if c.id in contact_ids]
    for contact in selected:
        queue.add(contact.to_dict(), campaign_id)

    # Si ce mailing provient d'une demande de diffusion, on la marque traitée
    # maintenant qu'elle a réellement été mise en file d'envoi
    submission_id = tpl.get('submission_id')
    if submission_id:
        import imap_submissions
        import shutil
        try:
            imap_submissions.mark_processed(Config, submission_id)
        except Exception as e:
            flash(f'Campagne créée, mais erreur lors du classement de la demande : {e}', 'error')
        shutil.rmtree(f'data/attachments/submission_{submission_id}', ignore_errors=True)

    # Confirmation = déclenchement : on ENVOIE tout de suite les contacts qu'on vient
    # de mettre en file. Si l'envoi est interrompu (timeout gros volume), la file garde
    # la progression → « Reprendre l'envoi » depuis la File d'attente termine le reste.
    _flash_send_result(_run_send(campaign_id))
    return redirect(url_for('mailing.queue', campaign=campaign_id))


@bp.route('/mailing/discard', methods=['POST'])
@login_required
def discard():
    """Abandonne un mailing en préparation : supprime le template et ses pièces
    jointes sur disque. Refuse si la campagne a déjà été mise en file d'envoi."""
    import shutil
    campaign_id = request.form.get('campaign_id')
    if campaign_id:
        camp = db.session.get(MailCampaign, campaign_id)
        already_queued = MailQueueItem.query.filter_by(campaign_id=campaign_id).first() is not None
        if camp and not already_queued:
            db.session.delete(camp)
            db.session.commit()
            shutil.rmtree(f'data/attachments/{campaign_id}', ignore_errors=True)
    flash('Mailing abandonné.', 'info')
    return redirect(url_for('mailing.history'))


@bp.route('/mailing/queue')
@login_required
def queue():
    """File d'attente.
    - Vue campagne (?campaign=…) : détail/revue de la campagne (tous les items).
    - Vue globale : UNIQUEMENT le NON-expédié (en attente + erreurs), groupé PAR
      CAMPAGNE. Une campagne 100 % envoyée n'a plus rien à faire ici → elle
      disparaît de la file (elle reste consultable dans l'historique)."""
    from mailer import MailQueue
    from collections import defaultdict

    campaign = request.args.get('campaign')
    queue = MailQueue()
    stats = queue.get_stats(campaign)

    if campaign:
        template = queue.get_campaign_template(campaign) or {}
        items = [i for i in queue.queue if i['campaign_id'] == campaign]
        return render_template('mailing_queue.html', items=items, stats=stats,
                               campaign=campaign, template=template, queue_campaigns=None)

    # Vue globale : regrouper le non-expédié par campagne
    groups = defaultdict(lambda: {'pending': 0, 'error': 0})
    for it in queue.queue:
        if it['status'] in ('pending', 'error'):
            groups[it['campaign_id']][it['status']] += 1
    queue_campaigns = []
    for cid, g in groups.items():
        tpl = queue.get_campaign_template(cid) or {}
        queue_campaigns.append({
            'campaign_id': cid,
            'name': tpl.get('name') or tpl.get('subject') or cid,
            'pending': g['pending'], 'error': g['error'],
            'remaining': g['pending'] + g['error']})
    queue_campaigns.sort(key=lambda c: (-c['remaining'], c['name'].lower()))

    return render_template('mailing_queue.html', items=None, stats=stats,
                           campaign=None, template={}, queue_campaigns=queue_campaigns)


def _run_send(campaign):
    """Envoie tous les emails EN ATTENTE d'une campagne (boucle synchrone, débit
    MAIL_RATE_PER_MINUTE) + copie récapitulative à l'expéditeur. Partagé par le parcours
    d'envoi (add_to_queue) et « Reprendre l'envoi » (process).
    Retourne (sent, errors) ; ou (None, message) si SMTP absent / template introuvable.
    NB : l'évolution vers l'ASYNCHRONE = confier cette fonction à un worker (déclenché
    « maintenant » ou par un timer) — même modèle « confirmation = déclenchement »."""
    from mailer import Mailer, EmailTemplate, MailQueue
    from pathlib import Path
    from helpers import get_setting
    import time

    if not Config.SMTP_HOST:
        return (None, 'SMTP non configuré', None)

    queue = MailQueue()
    pending = queue.get_pending(campaign)
    if not pending:
        return (0, 0, None)

    tpl = queue.get_campaign_template(campaign)
    if not tpl:
        return (None, 'Template de campagne introuvable', None)

    mailer = Mailer(
        smtp_host=Config.SMTP_HOST,
        smtp_port=Config.SMTP_PORT,
        smtp_user=Config.SMTP_USER,
        smtp_password=Config.SMTP_PASSWORD,
        sender_email=Config.SMTP_SENDER_EMAIL,
        sender_name=Config.SMTP_SENDER_NAME,
        use_tls=Config.SMTP_USE_TLS
    )

    mail_format = tpl.get('format', 'text')
    include_unsubscribe = tpl.get('include_unsubscribe', False)
    attachments = tpl.get('attachments', [])

    if mail_format == 'html':
        template = EmailTemplate(subject=tpl['subject'], body_text='', body_html=tpl['body'])
    else:
        template = EmailTemplate(subject=tpl['subject'], body_text=tpl['body'])

    delay = 60.0 / Config.MAIL_RATE_PER_MINUTE
    sent = 0
    errors = 0

    # Toggle « Gestion du bounce » (Paramètres) : OFF → pas de Return-Path bounce forcé
    # en enveloppe (évite le rejet SMTP 553 sur les serveurs stricts).
    bounce_on = get_setting('bounce_enabled', '1') != '0'
    bounce_return_path = (Config.BOUNCE_RETURN_PATH or Config.BOUNCE_IMAP_USER or None) if bounce_on else None

    from datetime import datetime as _dt
    sent_log = []   # (contact_id, sent_at) des envois réussis → journal ContactSend

    # Plafonds glissants (1h / 24h) tous envois confondus, via le journal ContactSend
    # (déjà envoyés lors des campagnes PRÉCÉDENTES) + le compteur `sent` de ce run.
    from datetime import timedelta
    _now = utcnow()

    def _sent_since(delta):
        return db.session.query(db.func.count(ContactSend.id)).filter(
            ContactSend.sent_at >= _now - delta).scalar() or 0

    prior_hour = _sent_since(timedelta(hours=1))
    prior_day = _sent_since(timedelta(days=1))
    max_hour, max_day = Config.MAIL_MAX_PER_HOUR, Config.MAIL_MAX_PER_DAY
    capped = None

    # UNE seule connexion SMTP pour toute la campagne (au lieu d'une par email).
    try:
        mailer.connect()
    except Exception as e:
        return (None, f'Connexion SMTP impossible : {e}', None)

    for item in pending:
        # Garde-fous anti-blocage : on s'arrête AVANT de dépasser les plafonds ;
        # les items non traités restent EN ATTENTE (repris via « Reprendre l'envoi »).
        if max_hour and (prior_hour + sent) >= max_hour:
            capped = f'plafond horaire atteint ({max_hour}/h)'
            break
        if max_day and (prior_day + sent) >= max_day:
            capped = f'plafond journalier atteint ({max_day}/j)'
            break
        contact = item['contact']

        # Construire l'URL de désabonnement par contact
        unsub_url = None
        if include_unsubscribe and contact.get('uid'):
            unsub_url = f"{Config.BASE_URL}/unsubscribe/{contact['uid']}"

        try:
            subj, body_text, body_html = template.render(contact, unsubscribe_url=unsub_url)
            mailer.send_single(contact['email'], subj, body_text, body_html,
                               unsubscribe_url=unsub_url, attachments=attachments,
                               return_path=bounce_return_path)
            queue.mark_sent(item['id'])
            sent += 1
            if contact.get('id'):
                sent_log.append((contact['id'], utcnow()))
        except Exception as e:
            queue.mark_error(item['id'], str(e))
            errors += 1
        time.sleep(delay)

    # Journal d'envoi par contact (best-effort : ne doit jamais casser l'envoi)
    if sent_log:
        try:
            for cid, ts in sent_log:
                db.session.add(ContactSend(contact_id=cid, campaign_id=campaign, sent_at=ts))
            db.session.commit()
        except Exception:
            db.session.rollback()

    # Copie récapitulative à l'expéditeur (best-effort)
    try:
        first_contact = pending[0]['contact']
        subj, body_text, body_html = template.render(first_contact)
        copy_subject = f"[Campagne {campaign} — {sent} envoyés, {errors} erreurs] {subj}"

        recap_text = (
            f"\n\n{'='*60}\n"
            f"RÉCAPITULATIF CAMPAGNE : {campaign}\n"
            f"{'='*60}\n"
            f"  Envoyés  : {sent}\n"
            f"  Erreurs  : {errors}\n"
            f"  Total    : {len(pending)}\n"
        )
        if errors > 0:
            failed = [i['contact']['email'] for i in pending if i['status'] == 'error']
            recap_text += f"\nEmails en erreur :\n" + "\n".join(f"  - {e}" for e in failed) + "\n"
        if attachments:
            recap_text += f"\nPièces jointes : {', '.join(Path(p).name for p in attachments)}\n"
        recap_text += f"{'='*60}\n"

        recap_html = (
            f'<hr><div style="font-family:monospace;font-size:13px;color:#555;background:#f5f5f5;padding:1rem;border-radius:4px;">'
            f'<strong>Récapitulatif — {campaign}</strong><br><br>'
            f'Envoyés : <strong>{sent}</strong> &nbsp;|&nbsp; '
            f'Erreurs : <strong style="color:{"#c00" if errors else "#090"}">{errors}</strong> &nbsp;|&nbsp; '
            f'Total : <strong>{len(pending)}</strong>'
        )
        if errors > 0:
            failed = [i['contact']['email'] for i in pending if i['status'] == 'error']
            recap_html += '<br><br>Emails en erreur :<br>' + '<br>'.join(f'&nbsp;• {e}' for e in failed)
        if attachments:
            recap_html += f'<br><br>Pièces jointes : {", ".join(Path(p).name for p in attachments)}'
        recap_html += '</div>'

        copy_body_text = body_text + recap_text
        copy_body_html = (body_html + recap_html) if body_html else None

        mailer.send_single(Config.SMTP_SENDER_EMAIL, copy_subject,
                           copy_body_text, copy_body_html, attachments=attachments)
    except Exception as e:
        flash(f'Copie expéditeur non envoyée : {e}', 'warning')

    mailer.quit()   # ferme la connexion SMTP persistante de la campagne
    return (sent, errors, capped)


def _flash_send_result(res):
    """Flash standard du résultat de _run_send (partagé par les 2 déclencheurs)."""
    sent, errors, capped = res
    if sent is None:
        flash(errors, 'error')   # `errors` porte le message dans le cas d'échec
        return
    if (sent, errors) == (0, 0) and not capped:
        flash('Aucun email en attente.', 'info')
        return
    if capped:
        flash(f'Envoi interrompu ({capped}) : {sent} envoyés, {errors} erreurs. '
              f'Le reste est EN FILE — reprenez plus tard (« Reprendre l\'envoi »).', 'warning')
    else:
        flash(f'Envoi terminé : {sent} envoyés, {errors} erreurs.',
              'success' if errors == 0 else 'warning')


@bp.route('/mailing/process', methods=['POST'])
@login_required
def process():
    """« Reprendre l'envoi » d'une campagne ayant encore des emails EN ATTENTE
    (depuis la File d'attente). L'envoi initial, lui, part directement de l'étape
    Destinataires (add_to_queue)."""
    campaign = request.form.get('campaign')
    _flash_send_result(_run_send(campaign))
    return redirect(url_for('mailing.queue', campaign=campaign))


@bp.route('/mailing/test-connection', methods=['POST'])
@login_required
def test_connection():
    """Teste une connexion avec la configuration `.env` COURANTE, sans rien modifier :
    - kind='smtp'   : envoi (SMTP)
    - kind='imap'   : boîte des demandes de diffusion (IMAP)
    - kind='bounce' : boîte des bounces (IMAP)
    Renvoie {success, error}."""
    import smtplib
    import ssl
    import imaplib

    kind = request.form.get('kind', 'smtp')
    try:
        if kind == 'imap':
            if not Config.IMAP_HOST:
                return jsonify({'success': False, 'error': 'Boîte des demandes (IMAP) non configurée'})
            conn = imaplib.IMAP4_SSL(Config.IMAP_HOST, Config.IMAP_PORT)
            conn.login(Config.IMAP_USER, Config.IMAP_PASSWORD)
            conn.select(Config.IMAP_FOLDER)
            conn.logout()
            return jsonify({'success': True})

        if kind == 'bounce':
            if not Config.BOUNCE_IMAP_HOST:
                return jsonify({'success': False, 'error': 'Boîte bounce (IMAP) non configurée'})
            conn = imaplib.IMAP4_SSL(Config.BOUNCE_IMAP_HOST, Config.BOUNCE_IMAP_PORT)
            conn.login(Config.BOUNCE_IMAP_USER, Config.BOUNCE_IMAP_PASSWORD)
            conn.select(Config.BOUNCE_IMAP_FOLDER)
            conn.logout()
            return jsonify({'success': True})

        # défaut : SMTP
        if not Config.SMTP_HOST:
            return jsonify({'success': False, 'error': 'SMTP non configuré'})
        context = ssl.create_default_context()
        if Config.SMTP_USE_TLS:
            with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                server.starttls(context=context)
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        else:
            with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, context=context) as server:
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
