"""Blueprint formulaires : formulaires de préférences (CRUD admin) et la
page publique de gestion des préférences par contact (/p/<token>/<uid>).

Endpoints : formulaires.index, formulaires.new, formulaires.detail,
formulaires.edit, formulaires.delete, formulaires.public.
"""
import io
import csv
import re
import secrets
from datetime import datetime, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, session
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

from models import (db, Liste, Contact, PreferenceForm, PreferenceFormListe,
                    PreferenceResponse, FieldProposal, FormBlock, SurveyQuestion,
                    FormAccessCode)
from config import Config
from helpers import admin_required
import fields as fields_registry

bp = Blueprint('formulaires', __name__)

# --- OTP (M9, Phase 2) : code par email sécurisant le pré-remplissage d'un bloc « fiche » ---
OTP_TTL_MIN = 10          # durée de validité d'un code
OTP_COOLDOWN_S = 60       # délai mini entre deux envois (anti-flood boîte)
OTP_MAX_ATTEMPTS = 5      # essais erronés avant invalidation du code
OTP_SESSION_MIN = 20      # durée de la session « email vérifié »


@bp.route('/formulaires')
@login_required
def index():
    forms = (PreferenceForm.query.filter_by(is_archived=False)
             .order_by(PreferenceForm.created_at.desc()).all())
    archived = (PreferenceForm.query.filter_by(is_archived=True)
                .order_by(PreferenceForm.created_at.desc()).all())
    pending_by_form = dict(db.session.query(FieldProposal.form_id, db.func.count())
                           .filter(FieldProposal.status == 'pending', FieldProposal.is_test == False)
                           .group_by(FieldProposal.form_id).all())
    return render_template('formulaires.html', forms=forms, archived=archived,
                           pending_by_form=pending_by_form, now=datetime.utcnow())


@bp.route('/formulaires/new', methods=['GET', 'POST'])
@login_required
def new():
    listes = Liste.query.order_by(Liste.nom).all()
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        if not nom:
            flash('Le nom du formulaire est requis.', 'error')
            return render_template('formulaire_edit.html', form=None, listes=listes, locked=False,
                               now=datetime.utcnow(), pending=0,
                               field_groups=fields_registry.fields_by_group(),
                               editable_keys=_editable_field_keys(),
                               fiche_selected=[], has_fiche=False,
                               sondage_block=None, has_sondage=False)
        pf = PreferenceForm(nom=nom,
                            description=request.form.get('description', '').strip() or None,
                            created_by_id=current_user.id)
        # Date de clôture optionnelle (même logique qu'à l'édition)
        raw_exp = request.form.get('expires_at', '').strip()
        if raw_exp:
            try:
                pf.expires_at = datetime.strptime(raw_exp, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            except ValueError:
                pass
        db.session.add(pf)
        db.session.flush()
        _save_form_listes(pf, request.form, listes)
        db.session.commit()
        flash(f'Formulaire "{pf.nom}" créé.', 'success')
        return redirect(url_for('formulaires.detail', id=pf.id, tab='lien'))
    return render_template('formulaire_edit.html', form=None, listes=listes, locked=False,
                           now=datetime.utcnow(), pending=0,
                           field_groups=fields_registry.fields_by_group(),
                           editable_keys=_editable_field_keys(),
                           fiche_selected=[], has_fiche=False,
                           sondage_block=None, has_sondage=False)


@bp.route('/formulaires/<int:id>', methods=['GET'])
@login_required
def detail(id):
    pf = PreferenceForm.query.get_or_404(id)
    # URL PUBLIQUE configurée (pas request.host_url, qui vaut l'hôte interne
    # http://127.0.0.1:8100 derrière nginx → liens morts pour les destinataires).
    base_url = (Config.BASE_URL or request.host_url).rstrip('/')
    link_template = f"{base_url}/p/{pf.token}/{{uid}}"
    responses = (PreferenceResponse.query
                 .filter_by(form_id=pf.id, is_test=False)
                 .order_by(PreferenceResponse.submitted_at.desc()).all())
    tab = request.args.get('tab', 'reponses')
    if tab not in ('lien', 'reponses', 'valider'):
        tab = 'reponses'
    props = (FieldProposal.query.filter_by(form_id=pf.id, status='pending', is_test=False)
             .order_by(FieldProposal.contact_id, FieldProposal.proposed_at).all())
    grouped = {}
    for p in props:
        grouped.setdefault(p.contact_id, []).append(p)
    proposal_groups = [{'contact': items[0].contact,
                        'proposed_at': max(i.proposed_at for i in items),
                        'items': items} for items in grouped.values()]
    liste_names = {l.id: l.nom for l in Liste.query.all()}
    question_labels = {}
    for b in pf.blocks:
        if b.type == 'sondage':
            for q in b.questions:
                question_labels[str(q.id)] = q.label
    return render_template('formulaire_detail.html', form=pf,
                           link_template=link_template, responses=responses,
                           tab=tab, proposal_groups=proposal_groups, pending=len(props),
                           field_map=fields_registry.field_map(),
                           liste_names=liste_names, question_labels=question_labels,
                           now=datetime.utcnow())


def _csv_safe(val):
    """Anti-injection de formules (Excel/Sheets) : préfixe d'un ' les valeurs
    commençant par = + - @ (ou tab/CR). Point « auth ≠ sanitisation » du TODO."""
    s = '' if val is None else str(val)
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s


@bp.route('/formulaires/<int:id>/reponses/export')
@admin_required
def export_responses(id):
    """Export CSV des réponses d'un formulaire (listes choisies + réponses de sondage), échappé."""
    pf = PreferenceForm.query.get_or_404(id)
    responses = (PreferenceResponse.query.filter_by(form_id=pf.id, is_test=False)
                 .order_by(PreferenceResponse.submitted_at.desc()).all())
    liste_names = {l.id: l.nom for l in Liste.query.all()}
    questions = []
    for b in sorted(pf.blocks, key=lambda x: x.ordre):
        if b.type == 'sondage':
            questions += sorted(b.questions, key=lambda x: x.ordre)

    out = io.StringIO()
    w = csv.writer(out)
    header = ['Nom', 'Prénom', 'Email', 'Répondu le', 'Listes choisies'] + [q.label for q in questions]
    w.writerow([_csv_safe(h) for h in header])
    for r in responses:
        ct = r.contact
        data = r.data or {}
        listes = ', '.join(liste_names.get(i, '#' + str(i)) for i in (data.get('listes') or []))
        survey = data.get('survey') or {}
        row = [ct.nom if ct else '', ct.prenom if ct else '', ct.email if ct else '',
               r.submitted_at.strftime('%d/%m/%Y %H:%M') if r.submitted_at else '', listes]
        row += [survey.get(str(q.id), '') for q in questions]
        w.writerow([_csv_safe(v) for v in row])

    slug = re.sub(r'[^a-zA-Z0-9]+', '_', pf.nom or '').strip('_') or f'form{pf.id}'
    fname = f'reponses_{slug}.csv'
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={fname}'})


def _render_edit_form(pf, listes, form_data):
    """Ré-affiche l'éditeur en PRÉSERVANT la saisie (échec de validation).

    Évite le piège du `redirect()` qui perdait tout le POST — notamment le bloc
    « fiche » ajouté côté JS (input `block_types`) et les champs cochés
    (`fiche_fields`), qui disparaissaient silencieusement. On reflète la saisie dans
    l'objet `pf` en mémoire (NON commité : annulé au teardown de session) pour un
    rendu fidèle, et on recalcule l'état des blocs depuis le POST (pas depuis la base)."""
    block_types = form_data.getlist('block_types')
    editable = _editable_field_keys()
    pf.nom = form_data.get('nom', '').strip()
    pf.description = form_data.get('description', '').strip() or None
    pf.is_active = form_data.get('is_active') == 'on'
    raw_exp = form_data.get('expires_at', '').strip()
    if raw_exp:
        try:
            pf.expires_at = datetime.strptime(raw_exp, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        except ValueError:
            pass
    else:
        pf.expires_at = None
    return render_template('formulaire_edit.html', form=pf, listes=listes,
                           locked=(len(pf.real_responses) > 0), now=datetime.utcnow(),
                           pending=FieldProposal.query.filter_by(form_id=pf.id, status='pending', is_test=False).count(),
                           field_groups=fields_registry.fields_by_group(),
                           editable_keys=editable,
                           fiche_selected=[k for k in form_data.getlist('fiche_fields') if k in editable],
                           has_fiche=('fiche' in block_types),
                           sondage_block=next((b for b in pf.blocks if b.type == 'sondage'), None),
                           has_sondage=('sondage' in block_types))


@bp.route('/formulaires/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    pf = PreferenceForm.query.get_or_404(id)
    listes = Liste.query.order_by(Liste.nom).all()
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        if not nom:
            flash('Le nom du formulaire est requis.', 'error')
            return _render_edit_form(pf, listes, request.form)
        # Garde-fou : une date de clôture est obligatoire dès qu'un bloc « fiche »
        # est exposé (limite la fenêtre de fuite du lien d'accès).
        # ⚠️ On RÉ-AFFICHE (pas de redirect) pour ne pas perdre le bloc fiche saisi.
        if 'fiche' in request.form.getlist('block_types') and not request.form.get('expires_at', '').strip():
            flash("Une date de clôture est obligatoire quand un bloc « Champs de fiche » est présent "
                  "(elle limite la durée de vie du lien d'accès).", 'error')
            return _render_edit_form(pf, listes, request.form)

        # Verrou structurel affiné (#21) : le JEU de groupes n'est figé QUE si le
        # formulaire a DÉJÀ des réponses (des contacts y ont répondu). Un formulaire
        # jamais utilisé reste librement restructurable, même actif.
        was_locked = len(pf.real_responses) > 0
        pf.nom = nom
        pf.description = request.form.get('description', '').strip() or None
        pf.is_active = request.form.get('is_active') == 'on'
        raw_exp = request.form.get('expires_at', '').strip()
        if raw_exp:
            try:
                pf.expires_at = datetime.strptime(raw_exp, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            except ValueError:
                pass
        else:
            pf.expires_at = None
        if was_locked:
            _update_form_listes_texts(pf, request.form)   # verrou : jeu de blocs/groupes figé, ordre/libellés OK
        else:
            _save_blocks(pf, request.form)                # jeu de blocs (fiche add/remove + whitelist)
            for fl in pf.listes:
                db.session.delete(fl)
            db.session.flush()
            _save_form_listes(pf, request.form, listes)
        db.session.commit()
        flash('Formulaire mis à jour.' + (' Groupes verrouillés (des réponses existent) : seuls libellés, aides et ordre ont été enregistrés.' if was_locked else ''), 'success')
        return redirect(url_for('formulaires.detail', id=pf.id, tab='lien'))
    locked = len(pf.real_responses) > 0
    pending = FieldProposal.query.filter_by(form_id=pf.id, status='pending', is_test=False).count()
    fiche_block = next((b for b in pf.blocks if b.type == 'fiche'), None)
    sondage_block = next((b for b in pf.blocks if b.type == 'sondage'), None)
    return render_template('formulaire_edit.html', form=pf, listes=listes, locked=locked,
                           now=datetime.utcnow(), pending=pending,
                           field_groups=fields_registry.fields_by_group(),
                           editable_keys=_editable_field_keys(),
                           fiche_selected=((fiche_block.config or {}).get('fields', []) if fiche_block else []),
                           has_fiche=bool(fiche_block),
                           sondage_block=sondage_block, has_sondage=bool(sondage_block))


@bp.route('/formulaires/<int:id>/delete', methods=['POST'])
@admin_required
def delete(id):
    """Suppression définitive (admin). Réservée aux formulaires déjà archivés :
    l'utilisateur archive, l'admin purge. Supprime aussi les réponses (cascade)."""
    pf = PreferenceForm.query.get_or_404(id)
    if not pf.is_archived:
        flash("Un formulaire doit d'abord être archivé avant de pouvoir être supprimé.", 'error')
        return redirect(url_for('formulaires.index'))
    nom = pf.nom
    # Nettoyage des enregistrements form-scopés sans cascade relationnelle (sinon orphelins).
    FormAccessCode.query.filter_by(form_id=pf.id).delete(synchronize_session=False)
    FieldProposal.query.filter_by(form_id=pf.id).delete(synchronize_session=False)
    db.session.delete(pf)   # cascade : listes, blocs, réponses
    db.session.commit()
    flash(f'Formulaire "{nom}" supprimé définitivement.', 'success')
    return redirect(url_for('formulaires.index'))


@bp.route('/formulaires/<int:id>/archive', methods=['POST'])
@login_required
def archive(id):
    """Archive un formulaire (masqué de la liste, réversible, réponses conservées).

    Autorisé uniquement si le formulaire est déjà clos : date de clôture
    (expires_at) renseignée ET dépassée. Sinon, l'utilisateur doit d'abord
    fixer une date de clôture passée — garde-fou contre un archivage accidentel
    d'un formulaire encore en cours de collecte."""
    pf = PreferenceForm.query.get_or_404(id)
    now = datetime.utcnow()
    still_online = pf.is_active and (pf.expires_at is None or pf.expires_at > now)
    if still_online:
        flash("Un formulaire actif et en ligne ne peut pas être archivé (il peut encore être "
              "utilisé). Clôturez-le d'abord — date de clôture passée, ou décochez « actif » "
              "dans Modifier — puis archivez-le.", 'error')
        return redirect(url_for('formulaires.index'))
    pf.is_archived = True
    db.session.commit()
    flash(f'Formulaire "{pf.nom}" archivé.', 'success')
    return redirect(url_for('formulaires.index'))


@bp.route('/formulaires/<int:id>/unarchive', methods=['POST'])
@login_required
def unarchive(id):
    """Désarchive un formulaire (le remet dans la liste active)."""
    pf = PreferenceForm.query.get_or_404(id)
    pf.is_archived = False
    db.session.commit()
    flash(f'Formulaire "{pf.nom}" désarchivé.', 'success')
    return redirect(url_for('formulaires.index'))


def _get_or_create_listes_block(pf):
    """Bloc 'listes' du formulaire (assembleur v2). Créé à la volée si absent."""
    blk = next((b for b in pf.blocks if b.type == 'listes'), None)
    if blk is None:
        blk = FormBlock(form_id=pf.id, type='listes', ordre=0)
        db.session.add(blk)
        db.session.flush()
    return blk


def _editable_field_keys():
    """Clés des champs de la fiche qu'un contact peut être autorisé à corriger
    (liste blanche = champs éditables du registre, hors e-mail verrouillé / système)."""
    return {f.key for f in fields_registry.contact_fields()
            if f.editable and f.key != 'email'}


def _save_blocks(pf, form_data):
    """Reconcilie le JEU de blocs (hors lignes de listes, gérées à part) d'après
    l'ordre soumis (`block_types`, dans l'ordre du DOM). Le bloc 'listes' reste
    obligatoire en M3b ; le bloc 'fiche' est ajoutable/retirable + sa liste blanche.
    À n'appeler QUE hors verrou (formulaire sans réponse)."""
    order = []
    for t in form_data.getlist('block_types'):
        if t in ('listes', 'fiche', 'sondage') and t not in order:
            order.append(t)
    if 'listes' not in order:
        order.insert(0, 'listes')
    existing = {b.type: b for b in pf.blocks}
    for i, t in enumerate(order):
        blk = existing.get(t)
        if blk is None:
            blk = FormBlock(form_id=pf.id, type=t, ordre=i)
            db.session.add(blk); db.session.flush()
            existing[t] = blk
        else:
            blk.ordre = i
        if t == 'fiche':
            allowed = _editable_field_keys()
            keys = [k for k in form_data.getlist('fiche_fields') if k in allowed]
            blk.config = {'fields': keys}
        elif t == 'sondage':
            for q in list(blk.questions):
                db.session.delete(q)
            db.session.flush()
            labels = form_data.getlist('q_label')
            types = form_data.getlist('q_type')
            o = 0
            for label, qtype in zip(labels, types):
                label = (label or '').strip()
                if not label:
                    continue
                if qtype not in ('oui_non', 'texte_court', 'texte_long'):
                    qtype = 'texte_court'
                db.session.add(SurveyQuestion(block_id=blk.id, ordre=o, label=label, type=qtype))
                o += 1
    for t, blk in list(existing.items()):
        if t not in order:
            db.session.delete(blk)   # cascade : questions ; les lignes de listes suivent l'ordre plus bas


def _save_form_listes(pf, form_data, all_listes):
    block = _get_or_create_listes_block(pf)
    liste_ids = form_data.getlist('liste_ids', type=int)
    for ordre, lid in enumerate(liste_ids):
        liste = next((l for l in all_listes if l.id == lid), None)
        if not liste:
            continue
        label = form_data.get(f'label_{lid}', '').strip() or liste.nom
        help_text = form_data.get(f'help_{lid}', '').strip() or None
        fl = PreferenceFormListe(form_id=pf.id, liste_id=lid, block_id=block.id,
                                 label=label, help_text=help_text, ordre=ordre)
        db.session.add(fl)


def _update_form_listes_texts(pf, form_data):
    """Verrou structurel : le JEU de groupes est figé (ajouts/retraits ignorés) mais
    on met à jour le libellé, l'aide ET l'ORDRE des groupes déjà présents, d'après la
    séquence soumise (liste_ids). Conforme à la règle « ouvert = ordre modifiable »."""
    existing = {fl.liste_id: fl for fl in pf.listes}
    ordre = 0
    for lid in form_data.getlist('liste_ids', type=int):
        fl = existing.get(lid)
        if fl is None:
            continue  # tentative d'ajout d'un groupe hors jeu → ignorée (verrou)
        fl.ordre = ordre
        ordre += 1
        label = form_data.get(f'label_{lid}', '').strip()
        if label:
            fl.label = label
        fl.help_text = form_data.get(f'help_{lid}', '').strip() or None


# --- Page publique ---

def _contact_field_value(contact, key):
    """Valeur canonique d'un champ de contact (colonne ou champ perso)."""
    fdef = fields_registry.field_map().get(key)
    if fdef and fdef.source == 'custom':
        return (contact.custom_fields or {}).get(key)
    return getattr(contact, key, None)


def _set_contact_field(contact, key, value):
    """Écrit une valeur sur un champ de contact (colonne ou champ perso)."""
    fdef = fields_registry.field_map().get(key)
    if fdef and fdef.source == 'custom':
        cf = dict(contact.custom_fields or {})
        if value:
            cf[key] = value
        else:
            cf.pop(key, None)
        contact.custom_fields = cf or None
    else:
        setattr(contact, key, value)


@bp.route('/formulaires/<int:id>/valider/appliquer', methods=['POST'])
@login_required
def proposal_apply(id):
    """Applique à la fiche toutes les propositions en attente d'un contact (après relecture)."""
    PreferenceForm.query.get_or_404(id)
    contact_id = request.form.get('contact_id', type=int)
    contact = Contact.query.get(contact_id)
    props = FieldProposal.query.filter_by(form_id=id, contact_id=contact_id, status='pending', is_test=False).all()
    if not contact or not props:
        flash('Rien à appliquer.', 'error')
        return redirect(url_for('formulaires.detail', id=id, tab='valider'))
    now = datetime.utcnow()
    for p in props:
        _set_contact_field(contact, p.field_key, p.new_value)
        p.status = 'applied'
        p.reviewed_by_id = current_user.id
        p.reviewed_at = now
    contact.updated_by_id = current_user.id   # trace de l'application
    db.session.commit()
    flash(f'{len(props)} modification(s) appliquée(s) à la fiche de {contact.prenom} {contact.nom}.', 'success')
    return redirect(url_for('formulaires.detail', id=id, tab='valider'))


@bp.route('/formulaires/<int:id>/valider/rejeter', methods=['POST'])
@login_required
def proposal_reject(id):
    """Rejette (sans écrire) toutes les propositions en attente d'un contact."""
    PreferenceForm.query.get_or_404(id)
    contact_id = request.form.get('contact_id', type=int)
    props = FieldProposal.query.filter_by(form_id=id, contact_id=contact_id, status='pending', is_test=False).all()
    now = datetime.utcnow()
    for p in props:
        p.status = 'rejected'
        p.reviewed_by_id = current_user.id
        p.reviewed_at = now
    db.session.commit()
    flash(f'{len(props)} modification(s) rejetée(s).', 'info')
    return redirect(url_for('formulaires.detail', id=id, tab='valider'))


@bp.route('/formulaires/<int:id>/apercu')
@login_required
def apercu(id):
    """Aperçu admin de la page publique (lecture seule, aucune donnée enregistrée).
    N'exige pas l'OTP : c'est une prévisualisation côté admin."""
    pf = PreferenceForm.query.get_or_404(id)
    blocks = sorted(pf.blocks, key=lambda b: b.ordre)
    dummy = type('Preview', (), {'prenom': 'Aperçu', 'nom': '', 'email': None})()
    return render_template('preferences_public.html', form=pf, contact=dummy,
                           contact_liste_ids=set(), blocks=blocks,
                           field_map=fields_registry.field_map(),
                           field_options=fields_registry.field_options, preview=True,
                           fiche_values={}, email_verified=False)


# ─────────────────────────── OTP (bloc « fiche ») ───────────────────────────

def _form_has_fiche(pf):
    return any(b.type == 'fiche' for b in pf.blocks)


def _otp_skey(pf, uid):
    return f'otpok:{pf.id}:{uid}'


def _otp_verified(pf, uid):
    """La session porte-t-elle une vérification email encore valide pour ce (formulaire, contact) ?"""
    exp = session.get(_otp_skey(pf, uid))
    return bool(exp and exp > datetime.utcnow().timestamp())


def _set_otp_verified(pf, uid):
    session[_otp_skey(pf, uid)] = (datetime.utcnow() + timedelta(minutes=OTP_SESSION_MIN)).timestamp()


def _mask_email(email):
    if not email or '@' not in email:
        return '—'
    local, _, domain = email.partition('@')
    lead = local[0] if local else ''
    dparts = domain.split('.')
    dmask = (dparts[0][0] if dparts[0] else '') + '***'
    return f'{lead}***@{dmask}.{dparts[-1]}' if len(dparts) > 1 else f'{lead}***@{dmask}'


def _latest_code(pf, uid):
    return (FormAccessCode.query
            .filter_by(form_id=pf.id, contact_uid=uid)
            .order_by(FormAccessCode.created_at.desc()).first())


def _has_valid_code(pf, uid):
    now = datetime.utcnow()
    return (FormAccessCode.query
            .filter(FormAccessCode.form_id == pf.id, FormAccessCode.contact_uid == uid,
                    FormAccessCode.consumed.is_(False), FormAccessCode.expires_at > now)
            .count() > 0)


def _mail_otp(contact, pf, code):
    """Envoie le code par email. Retourne True si l'envoi a réussi."""
    if not contact.email:
        return False
    try:
        from mailer import Mailer
        mailer = Mailer(Config.SMTP_HOST, Config.SMTP_PORT, Config.SMTP_USER,
                        Config.SMTP_PASSWORD, Config.SMTP_SENDER_EMAIL,
                        Config.SMTP_SENDER_NAME, Config.SMTP_USE_TLS)
        subject = f'Votre code de vérification — {pf.nom}'
        body = (
            f"Bonjour,\n\n"
            f"Voici votre code pour accéder au formulaire « {pf.nom} » et vérifier vos informations :\n\n"
            f"    {code}\n\n"
            f"Ce code est valable {OTP_TTL_MIN} minutes. Ne le communiquez à personne.\n\n"
            f"Si vous n'êtes pas à l'origine de cette demande, ignorez simplement ce message."
        )
        return mailer.send_single(contact.email, subject, body)
    except Exception:
        return False


def _purge_access_codes(pf, uid, now):
    """Hygiène de la table OTP (minimisation RGPD + table bornée). Les codes morts sont
    déjà inertes (la vérif exige consumed=False AND expires_at>now) — on les efface pour
    ne rien conserver d'inutile :
      1. on ne garde qu'UN code par (formulaire, contact) : les anciens de ce contact
         partent (on est appelé juste avant d'en créer un nouveau, cooldown déjà évalué) ;
      2. balayage global des codes oubliés depuis > 24 h (contacts qui ne reviennent pas).
    Pas de planificateur : le nettoyage se fait à l'occasion de chaque envoi."""
    FormAccessCode.query.filter_by(form_id=pf.id, contact_uid=uid).delete(synchronize_session=False)
    FormAccessCode.query.filter(
        FormAccessCode.expires_at < now - timedelta(hours=24)).delete(synchronize_session=False)


def _send_otp(pf, contact):
    """Génère + envoie un code (anti-flood). Retourne 'sent' | 'cooldown' | 'error'."""
    now = datetime.utcnow()
    latest = _latest_code(pf, contact.uid)
    if latest and (now - latest.created_at).total_seconds() < OTP_COOLDOWN_S:
        return 'cooldown'
    _purge_access_codes(pf, contact.uid, now)   # hygiène : ≤ 1 code/contact + balayage 24 h
    code = f'{secrets.randbelow(1000000):06d}'
    rec = FormAccessCode(
        form_id=pf.id, contact_uid=contact.uid,
        code_hash=generate_password_hash(code),
        created_at=now, expires_at=now + timedelta(minutes=OTP_TTL_MIN),
        attempts=0, consumed=False)
    db.session.add(rec)
    db.session.commit()
    return 'sent' if _mail_otp(contact, pf, code) else 'error'


def _is_test_req():
    """L'accès porte-t-il le marqueur d'envoi test (?test=1 ou champ caché) ?
    Propagé de bout en bout pour taguer la donnée is_test sans la faire compter comme réelle."""
    return request.args.get('test') == '1' or request.form.get('test') == '1'


def _public_url(form_token, contact_uid, test):
    return url_for('formulaires.public', form_token=form_token, contact_uid=contact_uid,
                   **({'test': '1'} if test else {}))


@bp.route('/p/<form_token>/<contact_uid>/code', methods=['POST'])
def request_code(form_token, contact_uid):
    """(Re)envoi d'un code à la demande depuis l'écran de vérification."""
    pf = PreferenceForm.query.filter_by(token=form_token).first_or_404()
    if not pf.is_active or (pf.expires_at and pf.expires_at < datetime.utcnow()):
        return render_template('preferences_expired.html', form=pf)
    contact = Contact.query.filter_by(uid=contact_uid, is_deleted=False).first_or_404()
    status = _send_otp(pf, contact)
    if status == 'sent':
        flash(f'Un nouveau code a été envoyé à {_mask_email(contact.email)}.', 'success')
    elif status == 'cooldown':
        flash('Un code vient d\'être envoyé. Patientez une minute avant d\'en demander un autre.', 'error')
    else:
        flash('L\'envoi du code a échoué. Réessayez dans un instant.', 'error')
    return redirect(_public_url(form_token, contact_uid, _is_test_req()))


@bp.route('/p/<form_token>/<contact_uid>/verify', methods=['POST'])
def verify_code(form_token, contact_uid):
    """Vérifie le code saisi ; ouvre la session « email vérifié » en cas de succès."""
    pf = PreferenceForm.query.filter_by(token=form_token).first_or_404()
    if not pf.is_active or (pf.expires_at and pf.expires_at < datetime.utcnow()):
        return render_template('preferences_expired.html', form=pf)
    contact = Contact.query.filter_by(uid=contact_uid, is_deleted=False).first_or_404()
    entered = re.sub(r'\D', '', request.form.get('code', ''))[:6]

    now = datetime.utcnow()
    rec = (FormAccessCode.query
           .filter(FormAccessCode.form_id == pf.id, FormAccessCode.contact_uid == contact.uid,
                   FormAccessCode.consumed.is_(False), FormAccessCode.expires_at > now)
           .order_by(FormAccessCode.created_at.desc()).first())

    if not rec:
        flash('Ce code a expiré. Nous vous en avons envoyé un nouveau.', 'error')
        _send_otp(pf, contact)
    elif rec.attempts >= OTP_MAX_ATTEMPTS:
        rec.consumed = True
        db.session.commit()
        flash('Trop d\'essais. Un nouveau code vient de vous être envoyé.', 'error')
        _send_otp(pf, contact)
    elif entered and check_password_hash(rec.code_hash, entered):
        rec.consumed = True
        db.session.commit()
        _set_otp_verified(pf, contact.uid)
        flash('Email vérifié. Vous pouvez consulter et corriger vos informations.', 'success')
    else:
        rec.attempts += 1
        db.session.commit()
        left = max(0, OTP_MAX_ATTEMPTS - rec.attempts)
        flash(f'Code incorrect. Il vous reste {left} essai(s).', 'error')
    return redirect(_public_url(form_token, contact_uid, _is_test_req()))


@bp.route('/p/<form_token>/<contact_uid>', methods=['GET', 'POST'])
def public(form_token, contact_uid):
    pf = PreferenceForm.query.filter_by(token=form_token).first_or_404()
    if not pf.is_active or (pf.expires_at and pf.expires_at < datetime.utcnow()):
        return render_template('preferences_expired.html', form=pf)
    contact = Contact.query.filter_by(uid=contact_uid, is_deleted=False).first_or_404()
    blocks = sorted(pf.blocks, key=lambda b: b.ordre)
    needs_otp = _form_has_fiche(pf)

    # Bloc « fiche » présent → barrière OTP (gate complet) tant que l'email n'est pas vérifié.
    if needs_otp and not _otp_verified(pf, contact.uid):
        if request.method == 'GET' and not _has_valid_code(pf, contact.uid):
            _send_otp(pf, contact)   # 1er envoi automatique à l'ouverture (anti-flood via cooldown)
        return render_template('preferences_otp.html', form=pf, contact=contact,
                               masked_email=_mask_email(contact.email),
                               ttl_min=OTP_TTL_MIN, test=_is_test_req())

    if request.method == 'POST':
        data = {}
        is_test = _is_test_req()   # envoi test → donnée taguée is_test, exclue partout où « réel » compte
        # --- Bloc listes : appliqué directement sur Contact.listes ---
        if any(b.type == 'listes' for b in blocks):
            checked_ids = set(request.form.getlist('liste_ids', type=int))
            for fl in pf.listes:
                liste = fl.liste
                if fl.liste_id in checked_ids and liste not in contact.listes:
                    contact.listes.append(liste)
                elif fl.liste_id not in checked_ids and liste in contact.listes:
                    contact.listes.remove(liste)
            data['listes'] = sorted(checked_ids)
        # --- Bloc sondage : réponses stockées isolément (jamais sur la fiche) ---
        survey = {}
        for b in blocks:
            if b.type == 'sondage':
                for q in b.questions:
                    val = (request.form.get(f'survey_{q.id}', '') or '').strip()
                    if val:
                        survey[str(q.id)] = val
        if survey:
            data['survey'] = survey
        # --- Bloc fiche : propositions en attente de validation (jamais d'écriture directe) ---
        # On n'atteint ce POST QUE si l'email est vérifié (gate OTP en amont) → otp_verified.
        otp_ok = _otp_verified(pf, contact.uid)
        allowed = _editable_field_keys()
        for b in blocks:
            if b.type == 'fiche':
                for k in [k for k in (b.config or {}).get('fields', []) if k in allowed]:
                    newv = (request.form.get(f'fiche_{k}', '') or '').strip()
                    curv = _contact_field_value(contact, k)
                    # Dédup : une seule proposition « pending » par (formulaire, contact, champ),
                    # ISOLÉE par is_test (un test ne touche jamais une proposition réelle).
                    # Re-soumettre MET À JOUR l'existante au lieu d'en créer une nouvelle.
                    existing = FieldProposal.query.filter_by(
                        form_id=pf.id, contact_id=contact.id, field_key=k,
                        status='pending', is_test=is_test).first()
                    if newv and newv != (curv or ''):
                        if existing:
                            existing.old_value = curv
                            existing.new_value = newv
                            existing.otp_verified = otp_ok
                            existing.proposed_at = datetime.utcnow()
                        else:
                            db.session.add(FieldProposal(
                                form_id=pf.id, contact_id=contact.id, field_key=k,
                                old_value=curv, new_value=newv, status='pending',
                                otp_verified=otp_ok, is_test=is_test))
                    elif existing:
                        # Le contact est revenu à la valeur canonique (ou a vidé le champ) :
                        # la proposition en attente n'a plus lieu d'être → on la retire.
                        db.session.delete(existing)
        # Trace / met à jour la réponse (payload isolé). Ligne test et ligne réelle
        # sont indépendantes (filtre is_test) : un test n'écrase jamais une réponse réelle.
        resp = PreferenceResponse.query.filter_by(
            contact_id=contact.id, form_id=pf.id, is_test=is_test).first()
        if resp:
            resp.submitted_at = datetime.utcnow(); resp.data = data
        else:
            db.session.add(PreferenceResponse(contact_id=contact.id, form_id=pf.id,
                                              data=data, is_test=is_test))
        db.session.commit()
        return render_template('preferences_confirm.html', form=pf, contact=contact)

    # Pré-remplissage des champs de fiche (uniquement en session vérifiée — on n'arrive
    # ici avec un bloc fiche que si l'OTP est validé).
    allowed = _editable_field_keys()
    fiche_values = {}
    for b in blocks:
        if b.type == 'fiche':
            for k in [k for k in (b.config or {}).get('fields', []) if k in allowed]:
                fiche_values[k] = _contact_field_value(contact, k) or ''

    contact_liste_ids = {l.id for l in contact.listes}
    return render_template('preferences_public.html', form=pf, contact=contact,
                           contact_liste_ids=contact_liste_ids, blocks=blocks,
                           field_map=fields_registry.field_map(),
                           field_options=fields_registry.field_options, preview=False,
                           fiche_values=fiche_values, email_verified=needs_otp,
                           test=_is_test_req())
