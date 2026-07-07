"""Blueprint users : gestion des utilisateurs (admin) et profil personnel.

Endpoints : users.index, users.new, users.edit, users.delete,
users.toggle_active, users.profile.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash

from models import db, User, Contact
from helpers import admin_required

bp = Blueprint('users', __name__)


@bp.route('/users')
@admin_required
def index():
    users_list = User.query.order_by(User.username).all()
    return render_template('users.html', users=users_list)


@bp.route('/users/new', methods=['GET', 'POST'])
@admin_required
def new():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'user')

        if not username or not password:
            flash('Identifiant et mot de passe requis', 'error')
            contacts = Contact.query.filter(Contact.is_deleted == False).order_by(Contact.nom, Contact.prenom).all()
            return render_template('user_form.html', user=None, contacts=contacts)

        if User.query.filter_by(username=username).first():
            flash(f'L\'identifiant "{username}" existe déjà', 'error')
            contacts = Contact.query.filter(Contact.is_deleted == False).order_by(Contact.nom, Contact.prenom).all()
            return render_template('user_form.html', user=None, contacts=contacts)

        if role not in ('admin', 'user'):
            role = 'user'

        user = User(
            username=username,
            password_hash=generate_password_hash(password),
            nom=nom,
            prenom=prenom,
            email=email or None,
            role=role,
            is_active=True
        )
        db.session.add(user)
        try:
            db.session.commit()
            flash(f'Utilisateur "{username}" créé', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    contacts = Contact.query.filter(Contact.is_deleted == False).order_by(Contact.nom, Contact.prenom).all()
    return render_template('user_form.html', user=None, contacts=contacts)


@bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def edit(id):
    user = User.query.get_or_404(id)

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'user')
        password = request.form.get('password', '').strip()

        if not username:
            flash('Identifiant requis', 'error')
            contacts = Contact.query.filter(Contact.is_deleted == False).order_by(Contact.nom, Contact.prenom).all()
            return render_template('user_form.html', user=user, contacts=contacts)

        # Vérifier unicité du username si changé
        if username != user.username:
            if User.query.filter_by(username=username).first():
                flash(f'L\'identifiant "{username}" existe déjà', 'error')
                contacts = Contact.query.filter(Contact.is_deleted == False).order_by(Contact.nom, Contact.prenom).all()
                return render_template('user_form.html', user=user, contacts=contacts)

        if role not in ('admin', 'user'):
            role = 'user'

        contact_id = request.form.get('contact_id', type=int) or None

        user.username = username
        user.nom = nom
        user.prenom = prenom
        user.email = email or None
        user.role = role
        user.contact_id = contact_id

        if password:
            user.password_hash = generate_password_hash(password)

        try:
            db.session.commit()
            flash(f'Utilisateur "{username}" mis à jour', 'success')
            return redirect(url_for('users.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    contacts = Contact.query.filter(Contact.is_deleted == False).order_by(Contact.nom, Contact.prenom).all()
    return render_template('user_form.html', user=user, contacts=contacts)


@bp.route('/users/<int:id>/delete', methods=['POST'])
@admin_required
def delete(id):
    user = User.query.get_or_404(id)

    if user.id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte', 'error')
        return redirect(url_for('users.index'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Utilisateur "{username}" supprimé', 'success')
    return redirect(url_for('users.index'))


@bp.route('/users/<int:id>/toggle-active', methods=['POST'])
@admin_required
def toggle_active(id):
    user = User.query.get_or_404(id)

    if user.id == current_user.id:
        flash('Vous ne pouvez pas désactiver votre propre compte', 'error')
        return redirect(url_for('users.index'))

    user.is_active = not user.is_active
    db.session.commit()
    status = 'activé' if user.is_active else 'désactivé'
    flash(f'Compte "{user.username}" {status}', 'success')
    return redirect(url_for('users.index'))


@bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    if request.method == 'POST':
        current_user.nom = request.form.get('nom', '').strip()
        current_user.prenom = request.form.get('prenom', '').strip()
        current_user.email = request.form.get('email', '').strip() or None

        password = request.form.get('password', '').strip()
        password_confirm = request.form.get('password_confirm', '').strip()

        if password:
            if password != password_confirm:
                flash('Les mots de passe ne correspondent pas', 'error')
                return render_template('profile.html')
            current_user.password_hash = generate_password_hash(password)

        try:
            db.session.commit()
            flash('Profil mis à jour', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    return render_template('profile.html')
