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


@bp.route('/listes/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        liste = Liste(
            nom=request.form.get('nom', '').strip(),
            description=request.form.get('description', '').strip()
        )
        db.session.add(liste)
        try:
            db.session.commit()
            flash(f'Liste "{liste.nom}" créée', 'success')
            return redirect(url_for('listes.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    return render_template('liste_form.html', liste=None)


@bp.route('/listes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    liste = Liste.query.get_or_404(id)

    if request.method == 'POST':
        liste.nom = request.form.get('nom', '').strip()
        liste.description = request.form.get('description', '').strip()
        try:
            db.session.commit()
            flash(f'Liste mise à jour', 'success')
            return redirect(url_for('listes.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

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
