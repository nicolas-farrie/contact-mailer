"""Blueprint selection : la « sélection courante » = liste de travail transitoire de
l'utilisateur (objet ContactSet, clé `user:<id>`), accumulée entre recherches puis
actionnée (mailing, enregistrer comme liste, ajouter/retirer d'une liste, vider).

N'est PAS une Liste (pas de pollution de la page Listes). Voir contact_set.py.

Endpoints : selection.view, selection.add, selection.remove, selection.replace,
selection.clear, selection.save_as_list, selection.to_list, selection.from_list.
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, current_app)
from flask_login import login_required, current_user

from models import db, Contact, Liste
from contact_set import ContactSet
from blueprints.contacts import _filtered_contacts_query

bp = Blueprint('selection', __name__)


def _current():
    return ContactSet.for_user(current_user.id)


def _ids_from_request():
    """Ids visés par l'action : soit TOUS les résultats du filtre courant (scope=filter,
    le serveur rejoue la query — pas seulement la page affichée), soit les cases cochées."""
    if request.form.get('scope') == 'filter':
        return [c.id for c in _filtered_contacts_query(request.form).all()]
    return request.form.getlist('contact_ids', type=int)


def _back():
    """Retour à la page d'origine (garde les filtres), sinon la vue Sélection."""
    return redirect(request.form.get('back') or request.referrer or url_for('selection.view'))


@bp.route('/selection')
@login_required
def view():
    sel = _current()
    contacts = sel.contacts().all()
    listes = Liste.query.filter_by(is_archived=False).order_by(Liste.nom).all()
    return render_template('selection.html', contacts=contacts, listes=listes,
                           selection_count=len(contacts))


@bp.route('/selection/add', methods=['POST'])
@login_required
def add():
    ids = _ids_from_request()
    n = _current().add(ids)
    total = _current().count()
    if n:
        flash(f'{n} contact(s) ajouté(s) à la sélection (total : {total}).', 'success')
    else:
        flash('Aucun nouveau contact à ajouter (déjà dans la sélection).', 'info')
    return _back()


@bp.route('/selection/remove', methods=['POST'])
@login_required
def remove():
    ids = _ids_from_request()
    n = _current().remove(ids)
    flash(f'{n} contact(s) retiré(s) de la sélection (total : {_current().count()}).', 'success')
    return _back()


@bp.route('/selection/replace', methods=['POST'])
@login_required
def replace():
    ids = _ids_from_request()
    _current().replace(ids)
    flash(f'Sélection remplacée ({_current().count()} contact(s)).', 'success')
    return _back()


@bp.route('/selection/clear', methods=['POST'])
@login_required
def clear():
    n = _current().clear()
    flash(f'Sélection vidée ({n} contact(s) retiré(s)).', 'success')
    return _back()


@bp.route('/selection/save-as-list', methods=['POST'])
@login_required
def save_as_list():
    nom = (request.form.get('nom') or '').strip()
    if not nom:
        flash('Le nom de la liste est requis.', 'error')
        return _back()
    if Liste.query.filter(db.func.lower(Liste.nom) == nom.lower()).first():
        flash(f'Une liste nommée « {nom} » existe déjà. Choisissez un autre nom.', 'error')
        return _back()
    contacts = _current().contacts().all()
    if not contacts:
        flash('La sélection est vide : rien à enregistrer.', 'error')
        return _back()
    liste = Liste(nom=nom, description=(request.form.get('description') or '').strip(),
                  created_by_id=current_user.id)
    liste.contacts = contacts
    db.session.add(liste)
    try:
        db.session.commit()
        flash(f'Liste « {nom} » créée depuis la sélection ({len(contacts)} contact·s).', 'success')
    except Exception:
        db.session.rollback()
        flash('Impossible de créer la liste (nom déjà utilisé ?).', 'error')
    return redirect(url_for('selection.view'))


@bp.route('/selection/to-list', methods=['POST'])
@login_required
def to_list():
    liste = Liste.query.get(request.form.get('liste_id', type=int))
    if not liste:
        flash('Liste cible introuvable.', 'error')
        return _back()
    n = 0
    for contact in _current().contacts().all():
        if liste not in contact.listes:
            contact.listes.append(liste)
            n += 1
    db.session.commit()
    flash(f'{n} contact(s) de la sélection ajouté(s) à « {liste.nom} ».', 'success')
    return _back()


@bp.route('/selection/from-list', methods=['POST'])
@login_required
def from_list():
    liste = Liste.query.get(request.form.get('liste_id', type=int))
    if not liste:
        flash('Liste cible introuvable.', 'error')
        return _back()
    n = 0
    for contact in _current().contacts().all():
        if liste in contact.listes:
            contact.listes.remove(liste)
            n += 1
    db.session.commit()
    flash(f'{n} contact(s) de la sélection retiré(s) de « {liste.nom} ».', 'success')
    return _back()
