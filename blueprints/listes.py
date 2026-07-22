"""Blueprint listes : CRUD + archivage des listes de diffusion.

Endpoints : listes.index, listes.new, listes.edit, listes.archive,
listes.unarchive, listes.delete.
"""
import re

from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from models import db, Liste
from helpers import admin_required

bp = Blueprint('listes', __name__)

_HEX_RE = re.compile(r'^#[0-9a-fA-F]{6}$')


def _clean_color(raw):
    """N'accepte qu'un hex #rrggbb (sécurité : la couleur entre dans un style)."""
    raw = (raw or '').strip()
    return raw if _HEX_RE.match(raw) else None


def _duplicate_nom(nom, exclude_id=None):
    """Une autre liste porte-t-elle déjà ce nom (insensible à la casse) ?"""
    q = Liste.query.filter(db.func.lower(Liste.nom) == nom.lower())
    if exclude_id is not None:
        q = q.filter(Liste.id != exclude_id)
    return q.first() is not None


@bp.route('/listes')
@login_required
def index():
    actives = Liste.query.filter_by(is_archived=False).order_by(Liste.nom).all()
    archivees = Liste.query.filter_by(is_archived=True).order_by(Liste.nom).all()
    totals = {
        'listes': len(actives),
        'contacts': sum(l.count for l in actives),
        'joignables': sum(l.joignables for l in actives),
    }
    return render_template('listes.html', listes=actives, archivees=archivees, totals=totals)


@bp.route('/listes/new', methods=['POST'])
@login_required
def new():
    nom = request.form.get('nom', '').strip()
    description = request.form.get('description', '').strip()
    if not nom:
        flash('Le nom de la liste est requis.', 'error')
        return redirect(url_for('listes.index'))
    if _duplicate_nom(nom):
        flash(f'Une liste nommée « {nom} » existe déjà. Choisissez un autre nom.', 'error')
        return redirect(url_for('listes.index'))
    try:
        db.session.add(Liste(nom=nom, description=description,
                             color=_clean_color(request.form.get('color')),
                             created_by_id=current_user.id))
        db.session.commit()
        flash(f'Liste « {nom} » créée.', 'success')
    except Exception:
        db.session.rollback()
        flash('Impossible de créer la liste (nom déjà utilisé ?).', 'error')
    return redirect(url_for('listes.index'))


@bp.route('/listes/<int:id>/edit', methods=['POST'])
@login_required
def edit(id):
    liste = Liste.query.get_or_404(id)
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
        liste.color = _clean_color(request.form.get('color'))
        db.session.commit()
        flash('Liste mise à jour.', 'success')
    except Exception:
        db.session.rollback()
        flash('Impossible de mettre à jour la liste (nom déjà utilisé ?).', 'error')
    return redirect(url_for('listes.index'))


@bp.route('/listes/<int:id>/archive', methods=['POST'])
@login_required
def archive(id):
    liste = Liste.query.get_or_404(id)
    liste.is_archived = True
    db.session.commit()
    flash(f'Liste « {liste.nom} » archivée.', 'info')
    return redirect(url_for('listes.index'))


@bp.route('/listes/<int:id>/unarchive', methods=['POST'])
@login_required
def unarchive(id):
    liste = Liste.query.get_or_404(id)
    liste.is_archived = False
    db.session.commit()
    flash(f'Liste « {liste.nom} » restaurée.', 'success')
    return redirect(url_for('listes.index'))


@bp.route('/listes/<int:id>/delete', methods=['POST'])
@admin_required
def delete(id):
    """Suppression définitive (admin), uniquement depuis les archivées."""
    liste = Liste.query.get_or_404(id)
    if not liste.is_archived:
        flash('Archivez la liste avant de la supprimer définitivement.', 'error')
        return redirect(url_for('listes.index'))
    nom = liste.nom
    db.session.delete(liste)
    db.session.commit()
    flash(f'Liste « {nom} » supprimée définitivement.', 'info')
    return redirect(url_for('listes.index'))
