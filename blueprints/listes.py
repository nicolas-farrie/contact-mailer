"""Blueprint listes : CRUD des listes de diffusion.

Endpoints : listes.index, listes.new, listes.edit, listes.delete.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required

from models import db, Liste
from helpers import admin_required

bp = Blueprint('listes', __name__)


@bp.route('/listes')
@login_required
def index():
    listes_list = Liste.query.order_by(Liste.nom).all()
    totals = {
        'listes': len(listes_list),
        'contacts': sum(l.count for l in listes_list),
        'joignables': sum(l.joignables for l in listes_list),
    }
    return render_template('listes.html', listes=listes_list, totals=totals)


def _duplicate_nom(nom, exclude_id=None):
    """Une autre liste porte-t-elle déjà ce nom (insensible à la casse) ?"""
    q = Liste.query.filter(db.func.lower(Liste.nom) == nom.lower())
    if exclude_id is not None:
        q = q.filter(Liste.id != exclude_id)
    return q.first() is not None


@bp.route('/listes/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        description = request.form.get('description', '').strip()
        if not nom:
            flash('Le nom de la liste est requis.', 'error')
            return redirect(url_for('listes.index'))
        if _duplicate_nom(nom):
            flash(f'Une liste nommée « {nom} » existe déjà. Choisissez un autre nom.', 'error')
            return redirect(url_for('listes.index'))
        try:
            db.session.add(Liste(nom=nom, description=description))
            db.session.commit()
            flash(f'Liste « {nom} » créée.', 'success')
        except Exception:
            db.session.rollback()
            flash('Impossible de créer la liste (nom déjà utilisé ?).', 'error')
        return redirect(url_for('listes.index'))

    return render_template('liste_form.html', liste=None)


@bp.route('/listes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    liste = Liste.query.get_or_404(id)

    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        description = request.form.get('description', '').strip()
        if not nom:
            flash('Le nom de la liste est requis.', 'error')
            return redirect(url_for('listes.index'))
        if _duplicate_nom(nom, exclude_id=id):
            flash(f'Une autre liste nommée « {nom} » existe déjà.', 'error')
            return redirect(url_for('listes.index'))
        try:
            liste.nom = nom
            liste.description = description
            db.session.commit()
            flash('Liste mise à jour.', 'success')
        except Exception:
            db.session.rollback()
            flash('Impossible de mettre à jour la liste (nom déjà utilisé ?).', 'error')
        return redirect(url_for('listes.index'))

    return render_template('liste_form.html', liste=liste)


@bp.route('/listes/<int:id>/delete', methods=['POST'])
@admin_required
def delete(id):
    liste = Liste.query.get_or_404(id)
    nom = liste.nom
    db.session.delete(liste)
    db.session.commit()
    flash(f'Liste "{nom}" supprimée', 'success')
    return redirect(url_for('listes.index'))
