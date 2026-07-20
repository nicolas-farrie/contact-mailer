"""Blueprint contacts : liste/CRUD, actions en masse, bounces, réabonnement.

Endpoints : contacts.index, contacts.new, contacts.edit, contacts.delete,
contacts.bulk_action, contacts.scan_bounces, contacts.clear_bounce,
contacts.resubscribe.
"""
from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, Contact, Liste
from config import Config
from helpers import admin_required
import fields

bp = Blueprint('contacts', __name__)


def _apply_form(contact, form):
    """Écrit le formulaire sur le contact via le registre fields.py :
    colonnes éditables → attributs ; champs perso → contact.custom_fields.
    Les valeurs des champs perso désactivés (absents du registre) sont préservées."""
    custom = dict(contact.custom_fields or {})
    for f in fields.contact_fields():
        if not f.editable:
            continue
        val = (form.get(f.key) or '').strip()
        if f.source == 'custom':
            if val:
                custom[f.key] = val
            else:
                custom.pop(f.key, None)
        else:
            setattr(contact, f.key, val)
    contact.custom_fields = custom or None


def _apply_listes(contact, form, clear=False):
    if clear:
        contact.listes.clear()
    for lid in form.getlist('listes'):
        liste = Liste.query.get(int(lid))
        if liste and liste not in contact.listes:
            contact.listes.append(liste)


@bp.route('/')
@bp.route('/contacts')
@login_required
def index():
    liste_filter = request.args.get('liste', type=int)
    source_filter = request.args.get('source', '').strip()
    search = request.args.get('q', '').strip()

    query = Contact.query.filter(Contact.is_deleted == False)

    if liste_filter:
        liste = Liste.query.get(liste_filter)
        if liste:
            query = query.filter(Contact.listes.contains(liste))

    if source_filter:
        query = query.filter(Contact.source == source_filter)

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Contact.nom.ilike(search_pattern),
                Contact.prenom.ilike(search_pattern),
                Contact.email.ilike(search_pattern),
                Contact.organisation.ilike(search_pattern),
                Contact.adresse_ville.ilike(search_pattern)
            )
        )

    contacts_list = query.order_by(Contact.nom, Contact.prenom).all()
    listes = Liste.query.order_by(Liste.nom).all()
    # Sources distinctes pour le filtre
    sources = db.session.query(Contact.source).filter(Contact.is_deleted == False).distinct().order_by(Contact.source).all()
    sources = [s[0] for s in sources if s[0]]

    return render_template('contacts.html',
                           contacts=contacts_list,
                           listes=listes,
                           sources=sources,
                           liste_filter=liste_filter,
                           source_filter=source_filter,
                           search=search)


@bp.route('/contacts/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        contact = Contact(source='Manuel', created_by_id=current_user.id)
        _apply_form(contact, request.form)
        _apply_listes(contact, request.form)

        db.session.add(contact)
        try:
            db.session.commit()
            flash(f'Contact {contact.prenom} {contact.nom} créé', 'success')
            return redirect(url_for('contacts.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    listes = Liste.query.order_by(Liste.nom).all()
    return render_template('contact_form.html', contact=None, listes=listes)


@bp.route('/contacts/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    contact = Contact.query.get_or_404(id)

    if request.method == 'POST':
        back_liste = request.form.get('back_liste', '') or None
        _apply_form(contact, request.form)
        contact.updated_by_id = current_user.id
        _apply_listes(contact, request.form, clear=True)

        try:
            db.session.commit()
            flash(f'Contact mis à jour', 'success')
            return redirect(url_for('contacts.index', liste=back_liste) if back_liste else url_for('contacts.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    back_liste = request.args.get('back_liste', '') or None
    listes = Liste.query.order_by(Liste.nom).all()
    return render_template('contact_form.html', contact=contact, listes=listes, back_liste=back_liste)


@bp.route('/contacts/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    contact = Contact.query.get_or_404(id)
    nom_complet = f'{contact.prenom} {contact.nom}'
    contact.is_deleted = True
    contact.deleted_at = datetime.utcnow()
    contact.deleted_by_id = current_user.id
    db.session.commit()
    flash(f'Contact {nom_complet} déplacé dans la corbeille', 'success')
    back_liste = request.form.get('back_liste', '')
    return redirect(url_for('contacts.index', liste=back_liste) if back_liste else url_for('contacts.index'))


@bp.route('/contacts/bulk-action', methods=['POST'])
@login_required
def bulk_action():
    action = request.form.get('action')
    contact_ids = request.form.getlist('contact_ids')
    liste_id = request.form.get('liste_id', type=int)
    back_liste = request.form.get('back_liste')
    back_source = request.form.get('back_source')
    back_q = request.form.get('back_q')

    def redirect_back():
        params = {}
        if back_liste: params['liste'] = back_liste
        if back_source: params['source'] = back_source
        if back_q: params['q'] = back_q
        return redirect(url_for('contacts.index', **params))

    if not contact_ids:
        flash('Aucun contact sélectionné', 'error')
        return redirect_back()

    contacts = Contact.query.filter(Contact.id.in_(contact_ids)).all()
    liste = Liste.query.get(liste_id) if liste_id else None

    if action == 'add_to_liste' and liste:
        for contact in contacts:
            if liste not in contact.listes:
                contact.listes.append(liste)
        db.session.commit()
        flash(f'{len(contacts)} contacts ajoutés à "{liste.nom}"', 'success')

    elif action == 'remove_from_liste' and liste:
        for contact in contacts:
            if liste in contact.listes:
                contact.listes.remove(liste)
        db.session.commit()
        flash(f'{len(contacts)} contacts retirés de "{liste.nom}"', 'success')

    elif action == 'delete':
        now = datetime.utcnow()
        for contact in contacts:
            contact.is_deleted = True
            contact.deleted_at = now
            contact.deleted_by_id = current_user.id
        db.session.commit()
        flash(f'{len(contacts)} contacts déplacés dans la corbeille', 'success')

    return redirect_back()


@bp.route('/contacts/scan-bounces', methods=['POST'])
@login_required
def scan_bounces():
    from bounce_scanner import scan_bounces as _scan, mark_processed
    results = _scan(Config)
    if not results:
        flash('Aucun nouveau bounce détecté.', 'info')
        return redirect(url_for('contacts.index'))

    marked = 0
    skipped = 0
    for item in results:
        contact = Contact.query.filter(
            Contact.email.ilike(item['email']),
            Contact.is_deleted == False
        ).first()
        if contact:
            contact.has_bounced = True
            contact.bounced_at = datetime.utcnow()
            mark_processed(Config, item['imap_uid'])
            marked += 1
        else:
            skipped += 1

    db.session.commit()
    msg = f'{marked} bounce(s) enregistré(s)'
    if skipped:
        msg += f', {skipped} adresse(s) inconnue(s) ignorée(s)'
    flash(msg, 'warning' if marked else 'info')
    return redirect(url_for('contacts.index'))


@bp.route('/contacts/<int:id>/clear-bounce', methods=['POST'])
@admin_required
def clear_bounce(id):
    contact = Contact.query.get_or_404(id)
    contact.has_bounced = False
    contact.bounced_at = None
    db.session.commit()
    flash('Bounce réinitialisé.', 'success')
    return redirect(url_for('contacts.edit', id=id))


@bp.route('/contacts/<int:id>/resubscribe', methods=['POST'])
@login_required
def resubscribe(id):
    """Réabonner un contact (admin)"""
    contact = Contact.query.get_or_404(id)
    contact.is_unsubscribed = False
    contact.unsubscribed_at = None
    db.session.commit()
    flash(f'{contact.prenom} {contact.nom} a été réabonné', 'success')
    return redirect(url_for('contacts.edit', id=contact.id))
