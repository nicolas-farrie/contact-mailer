"""Blueprint settings : paramètres applicatifs (nom, apparence login) et
corbeille des contacts (restauration / purge).

Endpoints : settings.index, settings.clear_login_bg, settings.trash,
settings.trash_restore, settings.trash_purge.
"""
import os
import uuid

from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename

from models import db, Contact
from helpers import (admin_required, set_setting, _upload_dir,
                     _delete_current_login_bg, ALLOWED_IMAGE_EXT, MAX_IMAGE_BYTES)

bp = Blueprint('settings', __name__)


@bp.route('/settings', methods=['GET', 'POST'])
@admin_required
def index():
    if request.method == 'POST':
        section = request.form.get('section')

        if section == 'general':
            name = (request.form.get('app_name') or '').strip()
            if name:
                set_setting('app_name', name[:60])
                flash('Paramètres généraux enregistrés.', 'success')
            else:
                flash("Le nom de l'application ne peut pas être vide.", 'error')

        elif section == 'login_appearance':
            raw = request.form.get('login_overlay')
            if raw is not None and raw != '':
                try:
                    pct = max(0, min(70, int(float(raw))))
                    set_setting('login_overlay', str(pct / 100))
                except ValueError:
                    pass

            file = request.files.get('login_bg')
            if file and file.filename:
                ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
                if ext not in ALLOWED_IMAGE_EXT:
                    flash('Format non supporté (JPG, PNG ou WebP).', 'error')
                    return redirect(url_for('settings.index'))
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                if size > MAX_IMAGE_BYTES:
                    flash('Image trop volumineuse (5 Mo maximum).', 'error')
                    return redirect(url_for('settings.index'))
                fname = f'login_bg_{uuid.uuid4().hex}.{ext}'
                dest = os.path.join(_upload_dir(), secure_filename(fname))
                try:
                    from PIL import Image
                    img = Image.open(file.stream)
                    img.verify()
                    file.seek(0)
                    img = Image.open(file.stream)
                    img.save(dest)
                except Exception:
                    file.seek(0)
                    file.save(dest)
                _delete_current_login_bg()
                set_setting('login_bg_filename', os.path.basename(dest))
            flash('Apparence de la connexion enregistrée.', 'success')

        return redirect(url_for('settings.index'))

    deleted_contacts = Contact.query.filter(Contact.is_deleted == True).order_by(Contact.deleted_at.desc()).all()
    return render_template('settings.html', active_tab='general', deleted_contacts=deleted_contacts)


@bp.route('/settings/clear-login-bg', methods=['POST'])
@admin_required
def clear_login_bg():
    _delete_current_login_bg()
    set_setting('login_bg_filename', '')
    flash('Image de fond supprimée.', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/settings/trash')
@admin_required
def trash():
    deleted_contacts = Contact.query.filter(Contact.is_deleted == True).order_by(Contact.deleted_at.desc()).all()
    return render_template('settings.html', active_tab='settings', deleted_contacts=deleted_contacts)


@bp.route('/settings/trash/restore', methods=['POST'])
@admin_required
def trash_restore():
    ids = request.form.getlist('contact_ids', type=int)
    if not ids:
        flash('Aucun contact sélectionné', 'error')
        return redirect(url_for('settings.index'))
    contacts = Contact.query.filter(Contact.id.in_(ids), Contact.is_deleted == True).all()
    for c in contacts:
        c.is_deleted = False
        c.deleted_at = None
        c.deleted_by_id = None
    db.session.commit()
    flash(f'{len(contacts)} contact(s) restauré(s)', 'success')
    return redirect(url_for('settings.index'))


@bp.route('/settings/trash/purge', methods=['POST'])
@admin_required
def trash_purge():
    ids = request.form.getlist('contact_ids', type=int)
    if not ids:
        flash('Aucun contact sélectionné', 'error')
        return redirect(url_for('settings.index'))
    contacts = Contact.query.filter(Contact.id.in_(ids), Contact.is_deleted == True).all()
    count = len(contacts)
    for c in contacts:
        db.session.delete(c)
    db.session.commit()
    flash(f'{count} contact(s) supprimé(s) définitivement', 'success')
    return redirect(url_for('settings.index'))
