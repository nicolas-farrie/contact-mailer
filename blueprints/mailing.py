"""Blueprint mailing : composition et envoi des campagnes, file d'attente,
historique, demandes de diffusion (IMAP), preview et test SMTP.

Endpoints : mailing.compose, mailing.history, mailing.queue_retry,
mailing.history_archive/unarchive/delete, mailing.submissions,
mailing.submission_use/archive/attachment, mailing.preview, mailing.send,
mailing.confirm, mailing.add_to_queue, mailing.queue, mailing.process,
mailing.submission_preview, mailing.test_connection,
mailing.templates_list, mailing.template_save/rename/delete (modèles).
"""
import re
import unicodedata

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, send_from_directory)
from flask_login import login_required, current_user

from models import Contact, Liste, PreferenceForm, MailCampaign, MailTemplate, MailQueueItem, ContactSend, db, utcnow
from config import Config
from helpers import admin_required, listes_sorted, get_setting

bp = Blueprint('mailing', __name__)


# Bloc de signature en pied de mail : marqué (data-mail-sig) pour pouvoir le
# retirer proprement au ré-affichage / avant de le ré-appliquer (jamais d'accumulation).
# Matche aussi l'ancien bloc (sans marqueur) des campagnes créées avant ce correctif.
_SIG_RE = re.compile(
    r'\s*<p[^>]*(?:data-mail-sig="1"|color:#8a8a8a;font-size:12px)[^>]*>.*?</p>',
    re.DOTALL)


# Lien de formulaire dans un href, sans paramètre déjà présent (cf. send_test).
_TEST_FORM_LINK_RE = re.compile(r'(href=["\'][^"\']*/p/[^"\'?#\s]+)(?=["\'])', re.IGNORECASE)


def _strip_signature(body):
    """Retire tout bloc de signature déjà présent dans le corps (HTML)."""
    if not body:
        return body
    return _SIG_RE.sub('', body).rstrip()


# Coordonnées de l'association en pied de mail, marquées comme la signature pour être
# retirées puis ré-appliquées sans accumulation. Figées dans le corps à l'enregistrement
# de la campagne : l'aperçu montre exactement ce qui partira.
_ORG_RE = re.compile(r'\s*<div[^>]*data-mail-org="1"[^>]*>.*?</div>', re.DOTALL)


def _strip_org_footer(body):
    if not body:
        return body
    return _ORG_RE.sub('', body).rstrip()


def org_contact():
    """Coordonnées de l'association (Paramètres), '' si non renseignées."""
    return (get_setting('org_contact', '') or '').strip()


def _org_footer_body(body, mail_format, include):
    """Retire les coordonnées déjà présentes puis, si demandé et renseigné, les ajoute."""
    from markupsafe import escape
    body = _strip_org_footer(body) if mail_format == 'html' else body
    contact = org_contact()
    if not (include and contact):
        return body
    if mail_format == 'html':
        lines = '<br>'.join(str(escape(l)) for l in contact.splitlines() if l.strip())
        return (body + '<div data-mail-org="1" style="margin-top:16px;color:#8a8a8a;'
                f'font-size:12px;">{lines}</div>')
    return body + '\n\n' + contact


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


def _mailable(c):
    """Contact réellement joignable pour un envoi : ni désabonné, ni en erreur (bounce).
    Exclure has_bounced évite de re-présenter une adresse en erreur (dégrade la
    réputation SMTP — cf. reco LWS)."""
    return not c.is_unsubscribed and not c.has_bounced


def _recipients(liste_ids, use_selection=False):
    """Union DÉDOUBLONNÉE (par id) des contacts joignables (non supprimés, non
    désabonnés, NON EN ERREUR/bounce) des listes données ET — si `use_selection` — de
    la « sélection courante » de l'utilisateur. Un contact présent dans plusieurs
    sources n'apparaît qu'une fois. Ordre de première apparition (listes puis sélection)."""
    seen = {}
    for lid in liste_ids:
        liste = Liste.query.get(lid)
        if not liste:
            continue
        for c in liste.active_contacts:
            if _mailable(c) and c.id not in seen:
                seen[c.id] = c
    if use_selection:
        from contact_set import ContactSet
        for c in ContactSet.for_user(current_user.id).contacts().all():
            if _mailable(c) and c.id not in seen:
                seen[c.id] = c
    return list(seen.values())


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
    prefill = {'name': '', 'subject': '', 'body': '', 'format': 'text', 'liste_ids': [], 'reply_to': ''}
    campaign_attachments = []   # PJ déjà enregistrées (réutilisation / retour édition)
    from_campaign_id = None
    sign_checked = bool(current_user.moderation_signature)
    org_checked = bool(org_contact())   # coché par défaut dès que les coordonnées existent
    # Entrée « ★ Sélection courante » pré-cochée : deep-link depuis /selection, ou
    # réutilisation d'une campagne qui ciblait la sélection.
    use_selection_checked = request.args.get('from_selection') == '1'
    # Deep-link « écrire à cette liste » (depuis la page Listes) : pré-coche la liste
    # visée, comme ?from_selection=1 pré-coche la sélection courante.
    prefill['liste_ids'] = [i for i in request.args.getlist('liste', type=int)]
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
                'reply_to': tpl.get('reply_to', ''),
            }
            import os as _os
            campaign_attachments = [_os.path.basename(p) for p in (tpl.get('attachments') or [])]
            from_campaign_id = from_campaign
            use_selection_checked = use_selection_checked or bool(tpl.get('use_selection'))
            # La signature est un pied de mail, pas du contenu éditable : on la
            # retire du corps affiché (et on reflète l'état « signé »).
            sign_checked = bool(_SIG_RE.search(prefill['body']))
            org_checked = bool(_ORG_RE.search(prefill['body']))
            prefill['body'] = _strip_signature(_strip_org_footer(prefill['body']))

    # Pré-remplissage depuis un modèle : seulement le CONTENU. Appliqué après
    # from_campaign pour qu'un modèle choisi en cours d'édition garde la campagne,
    # ses listes et ses pièces jointes.
    template_id = request.args.get('modele', type=int)
    template_attachments = []
    if template_id:
        mt = db.session.get(MailTemplate, template_id)
        if mt:
            prefill.update({'subject': mt.subject or '', 'body': mt.body or '',
                            'format': mt.format or 'html', 'reply_to': mt.reply_to or ''})
            if not prefill.get('name'):
                prefill['name'] = mt.name
            sign_checked = mt.signed
            org_checked = mt.org_footer and bool(org_contact())
            template_attachments = list(mt.attachments or [])
        else:
            template_id = None
            flash('Modèle introuvable.', 'error')

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
    templates = MailTemplate.query.order_by(MailTemplate.name).all()
    from models import CustomFieldDefinition, CORE_MAIL_VARS
    custom_vars = [{'label': d.display_name, 'token': '{' + d.key + '}'}
                   for d in (CustomFieldDefinition.query.filter_by(is_active=True)
                             .order_by(CustomFieldDefinition.ordre).all())
                   if d.key not in CORE_MAIL_VARS]
    return render_template('mailing.html', listes=listes, smtp_configured=smtp_configured, prefill=prefill,
                           mail_templates=templates, template_id=template_id,
                           custom_vars=custom_vars,
                           template_attachments=template_attachments,
                           org_contact=org_contact(), org_checked=org_checked,
                           clear_local_draft=request.args.get('saved') == '1',
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
        for i, a in enumerate(sub['attachments'], 1):
            # secure_filename peut réduire un nom (non-ASCII, etc.) à '' → ne pas
            # perdre la PJ pour autant : nom de repli.
            filename = secure_filename(a['filename']) or f'piece-jointe-{i}'
            (attach_dir / filename).write_bytes(a['payload'])
            saved_attachments.append(filename)

        body = sub['body_html'] or sub['body_text']
        fmt = 'html' if sub['body_html'] else 'text'

        # Images du corps → fichiers, et `cid:` → lien vers ces fichiers. Les incorporer
        # au HTML (data URI) ajoutait un tiers du poids des images DANS le corps, qui
        # traverse ensuite la page, l'éditeur, le brouillon local et la requête d'aperçu :
        # 4 Mo de photos suffisaient à faire refuser l'aperçu par nginx (413) et à
        # dépasser le quota du navigateur, avec un brouillon périmé qui reprenait la main.
        if fmt == 'html' and sub.get('inline_images'):
            body = _externalize_inline_images(body, sub['inline_images'], attach_dir, uid)

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
    # Coup d'œil ponctuel : les images peuvent être incorporées au HTML, rien ne repart
    # ensuite dans une requête. C'est l'ÉDITEUR qui ne doit pas les porter (cf. submission_use).
    sub['body_html'] = imap_submissions.inline_as_data_uris(
        sub.get('body_html') or '', sub.get('inline_images'))
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


#: Sous-dossier des images du corps d'une demande, à côté de ses pièces jointes.
INLINE_DIR = 'inline'

#: Chemin servi pour ces images. Reconnu à l'envoi pour les réincorporer au message
#: (cf. mailer) : un mail qui pointerait vers notre application afficherait des images
#: cassées chez le destinataire, qui n'y a pas accès.
INLINE_URL_PREFIX = '/mailing/submission-inline/'


def _externalize_inline_images(body_html, inline_images, attach_dir, uid):
    """Écrit les images du corps sur disque et remplace les `cid:` par leur adresse.

    Le corps redevient léger : c'est lui qui voyage dans la page, l'éditeur, le brouillon
    local et la requête d'aperçu. Les images, elles, ne sont chargées qu'à l'affichage,
    une par une, et réincorporées au message au moment de l'envoi.
    """
    import mimetypes
    from pathlib import Path

    out_dir = Path(attach_dir) / INLINE_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    for i, (cid, (content_type, payload)) in enumerate(inline_images.items(), 1):
        ext = mimetypes.guess_extension(content_type) or '.img'
        # Nom dérivé du RANG, pas du Content-ID : celui-ci vient du message et peut
        # contenir n'importe quoi (chemins, caractères interdits).
        name = f'img{i}{ext}'
        (out_dir / name).write_bytes(payload)
        body_html = body_html.replace(f'cid:{cid}', f'{INLINE_URL_PREFIX}{uid}/{name}')
    return body_html


@bp.route('/mailing/submission-inline/<submission_id>/<filename>')
@login_required
def submission_inline(submission_id, filename):
    """Sert une image du corps d'une demande (cf. _externalize_inline_images).

    Mêmes précautions que les pièces jointes : seuls des types d'image sûrs sont servis
    inline, et `nosniff` empêche le navigateur de deviner un type exécutable.
    """
    from pathlib import Path
    import mimetypes
    d = Path(f'data/attachments/submission_{submission_id}/{INLINE_DIR}').absolute()
    mime, _ = mimetypes.guess_type(filename)
    if mime not in {'image/jpeg', 'image/png', 'image/gif', 'image/webp'}:
        return '', 404
    resp = send_from_directory(d, filename)
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


def _campaign_recipients(tpl):
    """Destinataires d'une campagne enregistrée : ses listes ET sa sélection courante.

    Point de passage UNIQUE : l'aperçu et l'envoi de test calculaient les destinataires
    à partir des seules listes, et une campagne ne visant que la sélection paraissait
    donc vide (aperçu renvoyé à l'éditeur).
    """
    return _recipients(_campaign_liste_ids(tpl), tpl.get('use_selection'))


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
    recipients = _campaign_recipients(tpl)
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
    recipients = _campaign_recipients(tpl) if tpl else []
    if not tpl or not recipients:
        flash('Campagne ou destinataires introuvables.', 'error')
        return redirect(back)

    contact = recipients[max(0, min(index, len(recipients) - 1))]
    subject, body, is_html = _render_campaign_for(tpl, contact)
    # Marqueur de TEST : on ajoute ?test=1 aux liens de formulaire (/p/<token>/<uid>)
    # UNIQUEMENT dans l'exemplaire de test → la soumission sera taguée is_test et
    # exclue partout (verrou, compteurs, export). Les campagnes réelles ne sont pas touchées.
    # Seulement dans les href : une image collée (data URI base64) peut contenir « /p/ »,
    # et le marqueur ajouté à sa suite cassait le lien entre l'image et sa pièce inline.
    body = _TEST_FORM_LINK_RE.sub(r'\1?test=1', body or '')
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

    reply_to = (request.form.get('reply_to') or '').strip() or None
    if reply_to and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', reply_to):
        return None, "L'adresse « Répondre à » n'est pas valide."

    if not ((liste_ids or use_selection) and subject and body):
        return None, 'Sélectionnez au moins une liste (ou la sélection courante), un sujet et un message.'

    if mail_format == 'html':
        body = _strip_org_footer(body)
    body = _sign_body(body, mail_format, request.form.get('sign') == 'on',
                      current_user.moderation_signature)
    body = _org_footer_body(body, mail_format, request.form.get('org_footer') == 'on')

    if not Config.SMTP_HOST:
        return None, 'SMTP non configuré'

    listes = Liste.query.filter(Liste.id.in_(liste_ids)).all()
    if liste_ids and not listes:
        return None, 'Liste(s) introuvable(s)'

    include_unsubscribe = request.form.get('include_unsubscribe') == 'on'

    # Union DÉDOUBLONNÉE des contacts JOIGNABLES (désabonnés + bounces exclus) :
    # listes + sélection courante
    recipients = _recipients(liste_ids, use_selection)
    all_active = [c for lst in listes for c in lst.active_contacts]
    if use_selection:
        from contact_set import ContactSet
        all_active += ContactSet.for_user(current_user.id).contacts().all()
    # Décompte détaillé des exclusions (dédoublonné par id)
    seen_ex = {}
    for c in all_active:
        if c.id not in seen_ex:
            seen_ex[c.id] = c
    n_unsub = sum(1 for c in seen_ex.values() if c.is_unsubscribed)
    n_bounce = sum(1 for c in seen_ex.values() if c.has_bounced and not c.is_unsubscribed)
    parts = []
    if n_unsub:
        parts.append(f'{n_unsub} désabonné{"s" if n_unsub > 1 else ""}')
    if n_bounce:
        parts.append(f'{n_bounce} en erreur (bounce)')
    if parts:
        flash(f'Exclus de l\'envoi : {", ".join(parts)}.', 'info')

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
    # PJ d'un modèle, gardées cochées par l'utilisateur
    template_attachments = set(request.form.getlist('template_attachments'))
    template = db.session.get(MailTemplate, request.form.get('template_id', type=int) or 0)
    if (uploaded_files and uploaded_files[0].filename) or included_submission_attachments \
            or kept_attachments or (template and template_attachments):
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

        # Reprendre les PJ du modèle
        if template and template_attachments:
            src_dir = Path(template.attachments_dir)
            for fn in template.attachments or []:
                src = src_dir / fn
                if fn in template_attachments and src.is_file():
                    dest = attach_dir / fn
                    shutil.copy(str(src), str(dest))
                    attachment_paths.append(str(dest))

    # Un même nom venu de deux sources (modèle + campagne reprise) n'est joint qu'une fois
    attachment_paths = list(dict.fromkeys(attachment_paths))

    # Sauvegarder le template (sans encore peupler la queue)
    MailQueue().set_campaign_template(campaign_id, subject, body, mail_format,
                                      sent_by=current_user.username,
                                      include_unsubscribe=include_unsubscribe,
                                      attachments=attachment_paths or None,
                                      liste_id=(liste_ids[0] if liste_ids else None),
                                      liste_ids=liste_ids, use_selection=use_selection,
                                      reply_to=reply_to,
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
    return redirect(url_for('mailing.compose', from_campaign=campaign_id, saved=1))


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


# === Modèles de mailing ===

@bp.route('/mailing/modeles')
@login_required
def templates_list():
    """Modèles partagés : tous les voient et les utilisent ; auteur et admins les gèrent."""
    templates = MailTemplate.query.order_by(MailTemplate.name).all()
    return render_template('mailing_modeles.html', templates=templates)


def _template_name_taken(name, exclude_id=None):
    q = MailTemplate.query.filter(db.func.lower(MailTemplate.name) == name.lower())
    if exclude_id:
        q = q.filter(MailTemplate.id != exclude_id)
    return db.session.query(q.exists()).scalar()


@bp.route('/mailing/modeles/save', methods=['POST'])
@login_required
def template_save():
    """Enregistre le contenu d'une campagne comme modèle (depuis l'aperçu)."""
    campaign_id = request.form.get('campaign_id')
    back = url_for('mailing.apercu', campaign=campaign_id)
    camp = db.session.get(MailCampaign, campaign_id) if campaign_id else None
    if not camp:
        flash('Campagne introuvable.', 'error')
        return redirect(url_for('mailing.compose'))
    name = (request.form.get('name') or '').strip()
    if not name:
        flash('Donnez un nom au modèle.', 'error')
        return redirect(back)
    if _template_name_taken(name):
        flash(f'Un modèle « {name} » existe déjà : choisissez un autre nom.', 'error')
        return redirect(back)

    body = camp.body or ''
    fmt = camp.format or 'text'
    if fmt == 'html':
        signed = bool(_SIG_RE.search(body))
        body = _strip_signature(body)   # la regex s'arrête au </p> : le bloc coordonnées reste
    else:
        sig = current_user.moderation_signature
        signed = bool(sig and body.endswith(f'\n\n— {sig}'))
        if signed:
            body = body[:-len(f'\n\n— {sig}')]
    org = bool(_ORG_RE.search(body)) if fmt == 'html' else False
    if org:
        body = _strip_org_footer(body)
    mt = MailTemplate(name=name, subject=camp.subject or '', body=body,
                      format=fmt, reply_to=camp.reply_to, signed=signed, org_footer=org,
                      created_by_id=current_user.id)
    db.session.add(mt)
    db.session.flush()   # id nécessaire au dossier des PJ

    import os, shutil
    names = []
    for src in camp.attachments or []:
        if os.path.isfile(src):
            os.makedirs(mt.attachments_dir, exist_ok=True)
            fn = os.path.basename(src)
            shutil.copy(src, os.path.join(mt.attachments_dir, fn))
            names.append(fn)
    mt.attachments = names or None
    db.session.commit()
    flash(f'Modèle « {name} » enregistré.', 'success')
    return redirect(back)


def _editable_template_or_none(template_id):
    mt = db.session.get(MailTemplate, template_id)
    if not mt:
        flash('Modèle introuvable.', 'error')
        return None
    if not mt.can_edit(current_user):
        flash("Seuls l'auteur du modèle et les administrateurs peuvent le modifier.", 'error')
        return None
    return mt


@bp.route('/mailing/modeles/<int:template_id>/rename', methods=['POST'])
@login_required
def template_rename(template_id):
    mt = _editable_template_or_none(template_id)
    if mt:
        name = (request.form.get('name') or '').strip()
        if not name:
            flash('Le nom ne peut pas être vide.', 'error')
        elif _template_name_taken(name, exclude_id=mt.id):
            flash(f'Un modèle « {name} » existe déjà.', 'error')
        else:
            mt.name = name
            db.session.commit()
            flash('Modèle renommé.', 'success')
    return redirect(url_for('mailing.templates_list'))


@bp.route('/mailing/modeles/<int:template_id>/delete', methods=['POST'])
@login_required
def template_delete(template_id):
    mt = _editable_template_or_none(template_id)
    if mt:
        import shutil
        name, folder = mt.name, mt.attachments_dir
        db.session.delete(mt)
        db.session.commit()
        shutil.rmtree(folder, ignore_errors=True)
        flash(f'Modèle « {name} » supprimé.', 'success')
    return redirect(url_for('mailing.templates_list'))


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

    listes = Liste.query.filter(Liste.id.in_(_campaign_liste_ids(tpl))).all()
    recipients = _campaign_recipients(tpl)

    return render_template('mailing_confirm.html',
                           campaign_id=campaign_id,
                           template=tpl,
                           listes=listes,
                           contacts=recipients)


@bp.route('/mailing/add-to-queue', methods=['POST'])
@login_required
def add_to_queue():
    """Parcours d'envoi (étape Destinataires) : met les contacts sélectionnés EN FILE.

    L'envoi lui-même est confié à `tools/process_queue.py`, lancé par un timer : une
    campagne de plusieurs centaines de mails s'étale toute seule au rythme autorisé,
    sans requête web qui attendrait des heures. « Envoyer maintenant » (send_now) reste
    disponible pour les petites listes, avec la même boucle et le même verrou."""
    from mailer import MailQueue
    campaign_id = request.form.get('campaign_id')
    contact_ids = set(request.form.getlist('contact_ids', type=int))

    if not campaign_id or not contact_ids:
        flash('Aucun contact sélectionné', 'error')
        return redirect(url_for('mailing.compose'))

    queue = MailQueue()
    tpl = queue.get_campaign_template(campaign_id)
    recipients = _campaign_recipients(tpl)

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

    if request.form.get('send_now') == '1':
        _flash_send_result(_run_send(campaign_id))
    else:
        flash(f'{len(selected)} email(s) mis en file : l\'envoi part tout seul, '
              f'par tranches, dans la limite du débit autorisé.', 'success')
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

    import sending

    campaign = request.args.get('campaign')
    queue = MailQueue()
    stats = queue.get_stats(campaign)
    # Marge restante dans l'heure et dans la journée : c'est ce qui explique un envoi
    # qui s'arrête tout seul, et quand le reste repartira.
    quota = sending.quota_state()
    paused = {c.id for c in MailCampaign.query.filter_by(paused=True).all()}
    # Qui envoie VRAIMENT en ce moment (verrou), plutôt qu'une déduction depuis les
    # compteurs : une campagne entamée puis arrêtée s'annonçait « en cours » sans fin.
    holder = sending.current_send()

    if campaign:
        template = queue.get_campaign_template(campaign) or {}
        items = [i for i in queue.queue if i['campaign_id'] == campaign]
        last_sent = (db.session.query(db.func.max(ContactSend.sent_at))
                     .filter(ContactSend.campaign_id == campaign).scalar())
        state, state_label, resume_at = sending.campaign_state(
            campaign, stats, paused=campaign in paused, holder=holder)
        return render_template('mailing_queue.html', items=items, stats=stats,
                               campaign=campaign, template=template, queue_campaigns=None,
                               quota=quota, is_paused=campaign in paused,
                               last_sent=last_sent, state=state, state_label=state_label,
                               resume_at=resume_at, now=sending.utcnow())

    # Vue globale : regrouper le non-expédié par campagne
    from datetime import datetime

    now = sending.utcnow()
    groups = defaultdict(lambda: {'pending': 0, 'error': 0, 'sent': 0,
                                  'deferred': 0, 'deferred_until': None})
    for it in queue.queue:
        g = groups[it['campaign_id']]
        if it['status'] in ('pending', 'error', 'sent'):
            g[it['status']] += 1
        if it['status'] == 'pending' and it.get('deferred_until'):
            until = datetime.fromisoformat(it['deferred_until'])
            if until > now:
                g['deferred'] += 1
                if g['deferred_until'] is None or until < g['deferred_until']:
                    g['deferred_until'] = until
    queue_campaigns = []
    for cid, g in groups.items():
        if not (g['pending'] or g['error']):
            continue          # campagne entièrement envoyée : elle appartient à l'historique
        tpl = queue.get_campaign_template(cid) or {}
        state, state_label, resume_at = sending.campaign_state(
            cid, g, paused=cid in paused, holder=holder)
        queue_campaigns.append({
            'campaign_id': cid,
            'name': tpl.get('name') or tpl.get('subject') or cid,
            'pending': g['pending'], 'error': g['error'],
            'sent': g['sent'],
            'paused': cid in paused,
            'state': state, 'state_label': state_label, 'resume_at': resume_at,
            'remaining': g['pending'] + g['error']})
    queue_campaigns.sort(key=lambda c: (-c['remaining'], c['name'].lower()))

    return render_template('mailing_queue.html', items=None, stats=stats,
                           campaign=None, template={}, queue_campaigns=queue_campaigns,
                           quota=quota, is_paused=False, last_sent=None, now=now)


def _run_send(campaign):
    """Envoi immédiat depuis l'interface (« Envoyer maintenant », « Reprendre l'envoi »).

    La boucle elle-même vit dans `sending.py`, partagée avec `tools/process_queue.py` :
    l'interface et le timer exécutent le même code, sous le MÊME verrou — deux envois
    simultanés doubleraient le débit vu par l'hébergeur.
    Retourne (sent, errors, stopped) ; (None, message, None) en cas d'échec."""
    import sending

    try:
        with sending.send_lock(campaign=campaign):
            sent, errors, stopped, warnings = sending.run_campaign(campaign)
    except sending.SendBusy:
        return (None, 'Un envoi est déjà en cours (envoi automatique ou autre '
                      'utilisateur) : le reste part tout seul, réessayez dans un moment.',
                None)
    for w in warnings:
        flash(w, 'warning')
    return (sent, errors, stopped)


def _flash_send_result(res):
    """Flash standard du résultat de _run_send (partagé par les 2 déclencheurs)."""
    import sending

    sent, errors, capped = res
    if sent is None:
        flash(errors, 'error')   # `errors` porte le message dans le cas d'échec
        return
    if (sent, errors) == (0, 0) and not capped:
        flash('Aucun email en attente.', 'info')
        return
    if capped:
        # « Reprenez plus tard » sans dire quand laissait le choix entre revenir
        # toutes les dix minutes et ne plus y penser du tout.
        when = sending.humanize_delay(capped.resume_at)
        suite = (f'Le reste part automatiquement {when}.' if when
                 else 'Le reste est EN FILE et repartira automatiquement.')
        flash(f'Tranche terminée ({capped}) : {sent} envoyés, {errors} erreurs. {suite}',
              'warning')
    else:
        flash(f'Envoi terminé : {sent} envoyés, {errors} erreurs.',
              'success' if errors == 0 else 'warning')


@bp.route('/mailing/queue/pause/<campaign_id>', methods=['POST'])
@login_required
def queue_pause(campaign_id):
    """Met en pause / reprend une campagne : ses mails restent en file, mais aucun envoi
    ne les traite tant qu'elle est en pause — ni le timer, ni « Envoyer maintenant »."""
    camp = db.session.get(MailCampaign, campaign_id)
    if camp:
        camp.paused = request.form.get('resume') != '1'
        db.session.commit()
        flash('Envoi mis en pause.' if camp.paused else 'Envoi repris : il redémarre au prochain passage.',
              'info' if camp.paused else 'success')
    return redirect(request.form.get('back') or url_for('mailing.queue'))


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
