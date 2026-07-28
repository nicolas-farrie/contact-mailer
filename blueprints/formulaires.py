"""Blueprint formulaires : formulaires de préférences (CRUD admin) et la
page publique de gestion des préférences par contact (/p/<token>/<uid>).

Endpoints : formulaires.index, formulaires.new, formulaires.detail,
formulaires.edit, formulaires.delete, formulaires.public.
"""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import (db, Liste, Contact, PreferenceForm, PreferenceFormListe,
                    PreferenceResponse, FieldProposal, FormBlock, SurveyQuestion)
from config import Config
from helpers import admin_required
import fields as fields_registry

bp = Blueprint('formulaires', __name__)


@bp.route('/formulaires')
@login_required
def index():
    forms = (PreferenceForm.query.filter_by(is_archived=False)
             .order_by(PreferenceForm.created_at.desc()).all())
    archived = (PreferenceForm.query.filter_by(is_archived=True)
                .order_by(PreferenceForm.created_at.desc()).all())
    return render_template('formulaires.html', forms=forms, archived=archived,
                           now=datetime.utcnow())


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
        return redirect(url_for('formulaires.detail', id=pf.id))
    return render_template('formulaire_edit.html', form=None, listes=listes)


@bp.route('/formulaires/<int:id>', methods=['GET'])
@login_required
def detail(id):
    pf = PreferenceForm.query.get_or_404(id)
    # URL PUBLIQUE configurée (pas request.host_url, qui vaut l'hôte interne
    # http://127.0.0.1:8100 derrière nginx → liens morts pour les destinataires).
    base_url = (Config.BASE_URL or request.host_url).rstrip('/')
    link_template = f"{base_url}/p/{pf.token}/{{uid}}"
    responses = (PreferenceResponse.query
                 .filter_by(form_id=pf.id)
                 .order_by(PreferenceResponse.submitted_at.desc()).all())
    tab = request.args.get('tab', 'reponses')
    if tab not in ('lien', 'reponses', 'valider'):
        tab = 'reponses'
    props = (FieldProposal.query.filter_by(form_id=pf.id, status='pending')
             .order_by(FieldProposal.contact_id, FieldProposal.proposed_at).all())
    grouped = {}
    for p in props:
        grouped.setdefault(p.contact_id, []).append(p)
    proposal_groups = [{'contact': items[0].contact,
                        'proposed_at': max(i.proposed_at for i in items),
                        'items': items} for items in grouped.values()]
    return render_template('formulaire_detail.html', form=pf,
                           link_template=link_template, responses=responses,
                           tab=tab, proposal_groups=proposal_groups, pending=len(props),
                           field_map=fields_registry.field_map(), now=datetime.utcnow())


@bp.route('/formulaires/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    pf = PreferenceForm.query.get_or_404(id)
    listes = Liste.query.order_by(Liste.nom).all()
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        if not nom:
            flash('Le nom du formulaire est requis.', 'error')
            return render_template('formulaire_edit.html', form=pf, listes=listes,
                                   locked=(len(pf.responses) > 0), now=datetime.utcnow(),
                                   pending=FieldProposal.query.filter_by(form_id=pf.id, status='pending').count())
        # Garde-fou : une date de clôture est obligatoire dès qu'un bloc « fiche »
        # est exposé (limite la fenêtre de fuite du lien d'accès).
        if 'fiche' in request.form.getlist('block_types') and not request.form.get('expires_at', '').strip():
            flash("Une date de clôture est obligatoire quand un bloc « Champs de fiche » est présent "
                  "(elle limite la durée de vie du lien d'accès).", 'error')
            return redirect(url_for('formulaires.edit', id=pf.id))

        # Verrou structurel affiné (#21) : le JEU de groupes n'est figé QUE si le
        # formulaire a DÉJÀ des réponses (des contacts y ont répondu). Un formulaire
        # jamais utilisé reste librement restructurable, même actif.
        was_locked = len(pf.responses) > 0
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
        return redirect(url_for('formulaires.detail', id=pf.id))
    locked = len(pf.responses) > 0
    pending = FieldProposal.query.filter_by(form_id=pf.id, status='pending').count()
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
    db.session.delete(pf)
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
    if not (pf.expires_at and pf.expires_at < now):
        flash("Seuls les formulaires dont la date de clôture est dépassée peuvent être "
              "archivés. Fixez d'abord une date de clôture passée (Modifier) pour clore "
              "le formulaire, puis archivez-le.", 'error')
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
    props = FieldProposal.query.filter_by(form_id=id, contact_id=contact_id, status='pending').all()
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
    props = FieldProposal.query.filter_by(form_id=id, contact_id=contact_id, status='pending').all()
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
                           field_options=fields_registry.field_options, preview=True)


@bp.route('/p/<form_token>/<contact_uid>', methods=['GET', 'POST'])
def public(form_token, contact_uid):
    pf = PreferenceForm.query.filter_by(token=form_token).first_or_404()
    if not pf.is_active or (pf.expires_at and pf.expires_at < datetime.utcnow()):
        return render_template('preferences_expired.html', form=pf)
    contact = Contact.query.filter_by(uid=contact_uid, is_deleted=False).first_or_404()
    blocks = sorted(pf.blocks, key=lambda b: b.ordre)

    if request.method == 'POST':
        data = {}
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
        # --- Bloc fiche : WRITE-ONLY → propositions en attente de validation (pas d'écriture directe) ---
        allowed = _editable_field_keys()
        for b in blocks:
            if b.type == 'fiche':
                for k in [k for k in (b.config or {}).get('fields', []) if k in allowed]:
                    newv = (request.form.get(f'fiche_{k}', '') or '').strip()
                    curv = _contact_field_value(contact, k)
                    if newv and newv != (curv or ''):
                        db.session.add(FieldProposal(
                            form_id=pf.id, contact_id=contact.id, field_key=k,
                            old_value=curv, new_value=newv, status='pending', otp_verified=False))
        # Trace / met à jour la réponse (payload isolé)
        resp = PreferenceResponse.query.filter_by(contact_id=contact.id, form_id=pf.id).first()
        if resp:
            resp.submitted_at = datetime.utcnow(); resp.data = data
        else:
            db.session.add(PreferenceResponse(contact_id=contact.id, form_id=pf.id, data=data))
        db.session.commit()
        return render_template('preferences_confirm.html', form=pf, contact=contact)

    contact_liste_ids = {l.id for l in contact.listes}
    return render_template('preferences_public.html', form=pf, contact=contact,
                           contact_liste_ids=contact_liste_ids, blocks=blocks,
                           field_map=fields_registry.field_map(),
                           field_options=fields_registry.field_options, preview=False)
