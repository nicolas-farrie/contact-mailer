"""Blueprint contacts : liste/CRUD, actions en masse, bounces, réabonnement.

Endpoints : contacts.index, contacts.new, contacts.edit, contacts.delete,
contacts.bulk_action, contacts.scan_bounces, contacts.clear_bounce,
contacts.resubscribe.
"""

from datetime import timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, Contact, Liste, ContactSend, utcnow
from config import Config
from helpers import admin_required
from contact_set import ContactSet
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
        # Ne réconcilier que les listes ACTIVES (celles proposées dans le formulaire).
        # Les adhésions à des listes archivées sont préservées (non affichées, non touchées).
        checked = set(form.getlist('listes'))
        for liste in list(contact.listes):
            if not liste.is_archived and str(liste.id) not in checked:
                contact.listes.remove(liste)
    for lid in form.getlist('listes'):
        liste = Liste.query.get(int(lid))
        if liste and liste not in contact.listes:
            contact.listes.append(liste)


def _filtered_contacts_query(args):
    """Query des contacts (non supprimés) filtrée selon les mêmes critères que la page
    Contacts (liste/source/statut/complétude/envoi/récent/recherche). SANS tri, pour
    être réutilisée par `index()` ET par l'ajout « tous les résultats du filtre » à la
    sélection courante (le serveur rejoue le filtre, pas seulement la page affichée)."""
    liste_filter = args.get('liste', type=int)
    source_filter = args.get('source', '').strip()
    search = args.get('q', '').strip()
    statut_filter = args.get('statut', '').strip()
    completude_filter = args.get('completude', '').strip()
    envoi_filter = args.get('envoi', '').strip()
    recent_filter = args.get('recent', '').strip()

    query = Contact.query.filter(Contact.is_deleted == False)

    if liste_filter:
        liste = Liste.query.get(liste_filter)
        if liste:
            query = query.filter(Contact.listes.contains(liste))

    if source_filter:
        query = query.filter(Contact.source == source_filter)

    # Statut = point coloré : abonné (vert) / désabonné (rouge) / bounce (ambre)
    if statut_filter == 'abonne':
        query = query.filter(Contact.is_unsubscribed == False, Contact.has_bounced == False)
    elif statut_filter == 'desabonne':
        query = query.filter(Contact.is_unsubscribed == True)
    elif statut_filter == 'bounce':
        query = query.filter(Contact.has_bounced == True)

    # Complétude = fiches « à compléter » (contacts importés sans coordonnées).
    # Un email/téléphone vide se stocke soit à NULL soit à '' selon l'origine.
    no_email = db.or_(Contact.email.is_(None), Contact.email == '')
    no_tel = db.or_(Contact.telephone.is_(None), Contact.telephone == '')
    if completude_filter == 'sans_email':
        query = query.filter(no_email)
    elif completude_filter == 'sans_tel':
        query = query.filter(no_tel)
    elif completude_filter == 'a_completer':
        query = query.filter(db.or_(no_email, no_tel))

    # Activité mailing : « jamais mailé » (aucun envoi journalisé) / « déjà mailé »
    # (au moins un envoi réussi), via le journal ContactSend (S1). EXISTS corrélé
    # (robuste aux NULL, contrairement à NOT IN (sous-requête)).
    if envoi_filter in ('jamais', 'deja'):
        sent = db.exists().where(ContactSend.contact_id == Contact.id)
        query = query.filter(sent if envoi_filter == 'deja' else ~sent)

    # Ajoutés récemment (created_at) — fenêtre glissante.
    if recent_filter in ('7', '30'):
        query = query.filter(Contact.created_at >= utcnow() - timedelta(days=int(recent_filter)))

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
    return query


@bp.route('/')
@bp.route('/contacts')
@login_required
def index():
    query = _filtered_contacts_query(request.args)
    recent_filter = request.args.get('recent', '').strip()

    # « Ajoutés récemment » → les plus récents d'abord ; sinon tri alphabétique.
    if recent_filter in ('7', '30'):
        contacts_list = query.order_by(Contact.created_at.desc()).all()
    else:
        contacts_list = query.order_by(Contact.nom, Contact.prenom).all()
    listes = Liste.query.filter_by(is_archived=False).order_by(Liste.nom).all()
    # Sources distinctes pour le filtre
    sources = db.session.query(Contact.source).filter(Contact.is_deleted == False).distinct().order_by(Contact.source).all()
    sources = [s[0] for s in sources if s[0]]

    return render_template('contacts.html',
                           contacts=contacts_list,
                           listes=listes,
                           sources=sources,
                           liste_filter=request.args.get('liste', type=int),
                           source_filter=request.args.get('source', '').strip(),
                           statut_filter=request.args.get('statut', '').strip(),
                           completude_filter=request.args.get('completude', '').strip(),
                           envoi_filter=request.args.get('envoi', '').strip(),
                           recent_filter=recent_filter,
                           search=request.args.get('q', '').strip(),
                           selection_ids=ContactSet.for_user(current_user.id).ids())


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

    listes = Liste.query.filter_by(is_archived=False).order_by(Liste.nom).all()
    return render_template('contact_form.html', contact=None, listes=listes)


@bp.route('/contacts/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    contact = Contact.query.get_or_404(id)

    if request.method == 'POST':
        back_liste = request.form.get('back_liste', '') or None
        ret_view = request.form.get('ret') == 'view'
        _apply_form(contact, request.form)
        contact.updated_by_id = current_user.id
        _apply_listes(contact, request.form, clear=True)

        try:
            db.session.commit()
            flash(f'Contact mis à jour', 'success')
            # Édition entamée depuis la fiche « vision » → on y retourne (garde la nav
            # Précédent/Suivant en session) ; sinon retour à la liste (comportement ✎).
            if ret_view:
                return redirect(url_for('contacts.view', id=contact.id, back_liste=back_liste or ''))
            return redirect(url_for('contacts.index', liste=back_liste) if back_liste else url_for('contacts.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    back_liste = request.args.get('back_liste', '') or None
    listes = Liste.query.filter_by(is_archived=False).order_by(Liste.nom).all()
    return render_template('contact_form.html', contact=contact, listes=listes,
                           back_liste=back_liste, from_view=(request.args.get('ret') == 'view'))


@bp.route('/contacts/<int:id>/view')
@login_required
def view(id):
    """Fiche en LECTURE SEULE (« vision ») + bouton Modifier. Un utilisateur qui suit
    un lien (ex. onglet Réponses d'un formulaire) n'atterrit plus directement en édition."""
    contact = Contact.query.get_or_404(id)
    back_liste = request.args.get('back_liste', '') or None
    listes = Liste.query.filter_by(is_archived=False).order_by(Liste.nom).all()
    return render_template('contact_form.html', contact=contact, listes=listes,
                           back_liste=back_liste, readonly=True)


@bp.route('/contacts/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    contact = Contact.query.get_or_404(id)
    nom_complet = f'{contact.prenom} {contact.nom}'
    contact.is_deleted = True
    contact.deleted_at = utcnow()
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

    elif action == 'transfer':
        source_id = request.form.get('source_liste_id', type=int)
        source = Liste.query.get(source_id) if source_id else None
        if liste and source:
            for contact in contacts:
                if source in contact.listes:
                    contact.listes.remove(source)
                if liste not in contact.listes:
                    contact.listes.append(liste)
            db.session.commit()
            flash(f'{len(contacts)} contacts transférés de "{source.nom}" vers "{liste.nom}"', 'success')
        else:
            flash('Transfert impossible : liste source ou cible manquante.', 'error')

    elif action == 'resubscribe':
        n = 0
        for contact in contacts:
            if contact.is_unsubscribed:
                contact.is_unsubscribed = False
                contact.unsubscribed_at = None
                contact.updated_by_id = current_user.id  # trace de l'acteur
                n += 1
        db.session.commit()
        flash(f'{n} contact(s) réabonné(s)', 'success')

    elif action == 'unsubscribe':
        now = utcnow()
        n = 0
        for contact in contacts:
            if not contact.is_unsubscribed:
                contact.is_unsubscribed = True
                contact.unsubscribed_at = now
                contact.updated_by_id = current_user.id  # trace de l'acteur
                n += 1
        db.session.commit()
        flash(f'{n} contact(s) désabonné(s)', 'success')

    elif action == 'delete':
        now = utcnow()
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
            contact.bounced_at = utcnow()
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
