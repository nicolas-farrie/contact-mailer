"""Blueprint formulaires : formulaires de préférences (CRUD admin) et la
page publique de gestion des préférences par contact (/p/<token>/<uid>).

Endpoints : formulaires.index, formulaires.new, formulaires.detail,
formulaires.edit, formulaires.delete, formulaires.public.
"""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import (db, Liste, Contact, PreferenceForm, PreferenceFormListe,
                    PreferenceResponse)
from config import Config
from helpers import admin_required

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
            return render_template('formulaire_edit.html', form=None, listes=listes)
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
    return render_template('formulaire_detail.html', form=pf,
                           link_template=link_template, responses=responses,
                           now=datetime.utcnow())


@bp.route('/formulaires/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    pf = PreferenceForm.query.get_or_404(id)
    listes = Liste.query.order_by(Liste.nom).all()
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        if not nom:
            flash('Le nom du formulaire est requis.', 'error')
            return render_template('formulaire_edit.html', form=pf, listes=listes)
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
        for fl in pf.listes:
            db.session.delete(fl)
        db.session.flush()
        _save_form_listes(pf, request.form, listes)
        db.session.commit()
        flash('Formulaire mis à jour.', 'success')
        return redirect(url_for('formulaires.detail', id=pf.id))
    return render_template('formulaire_edit.html', form=pf, listes=listes)


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


def _save_form_listes(pf, form_data, all_listes):
    liste_ids = form_data.getlist('liste_ids', type=int)
    for ordre, lid in enumerate(liste_ids):
        liste = next((l for l in all_listes if l.id == lid), None)
        if not liste:
            continue
        label = form_data.get(f'label_{lid}', '').strip() or liste.nom
        help_text = form_data.get(f'help_{lid}', '').strip() or None
        fl = PreferenceFormListe(form_id=pf.id, liste_id=lid,
                                 label=label, help_text=help_text, ordre=ordre)
        db.session.add(fl)


# --- Page publique ---

@bp.route('/p/<form_token>/<contact_uid>', methods=['GET', 'POST'])
def public(form_token, contact_uid):
    pf = PreferenceForm.query.filter_by(token=form_token).first_or_404()
    if not pf.is_active or (pf.expires_at and pf.expires_at < datetime.utcnow()):
        return render_template('preferences_expired.html', form=pf)
    contact = Contact.query.filter_by(uid=contact_uid, is_deleted=False).first_or_404()

    if request.method == 'POST':
        checked_ids = set(request.form.getlist('liste_ids', type=int))
        allowed_ids = {fl.liste_id for fl in pf.listes}
        for fl in pf.listes:
            liste = fl.liste
            if fl.liste_id in checked_ids:
                if liste not in contact.listes:
                    contact.listes.append(liste)
            else:
                if liste in contact.listes:
                    contact.listes.remove(liste)
        # Enregistre ou met à jour la trace
        resp = PreferenceResponse.query.filter_by(
            contact_id=contact.id, form_id=pf.id).first()
        if resp:
            resp.submitted_at = datetime.utcnow()
        else:
            db.session.add(PreferenceResponse(contact_id=contact.id, form_id=pf.id))
        db.session.commit()
        return render_template('preferences_confirm.html', form=pf, contact=contact)

    contact_liste_ids = {l.id for l in contact.listes}
    return render_template('preferences_public.html', form=pf, contact=contact,
                           contact_liste_ids=contact_liste_ids)
