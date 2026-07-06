"""Helpers partagés entre les blueprints : décorateur d'accès admin et
gestion des paramètres applicatifs (table Setting) + fichiers d'upload.

Utilise `current_app` plutôt que d'importer `app` (évite les imports circulaires).
"""
import os
from functools import wraps

from flask import current_app, url_for, flash, redirect
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, Setting


# === Contrôle d'accès ===

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Accès réservé aux administrateurs', 'error')
            return redirect(url_for('contacts.index'))
        return f(*args, **kwargs)
    return decorated


# === Paramètres applicatifs (table Setting) ===

SETTING_DEFAULTS = {
    'app_name': 'Contact Mailer',
    'login_bg_filename': '',
    'login_overlay': '0.35',
}
ALLOWED_IMAGE_EXT = {'png', 'jpg', 'jpeg', 'webp'}
MAX_IMAGE_BYTES = 5 * 1024 * 1024


def get_setting(key, default=None):
    row = Setting.query.get(key)
    if row is not None and row.value is not None:
        return row.value
    return SETTING_DEFAULTS.get(key, default)


def set_setting(key, value):
    row = Setting.query.get(key)
    if row is None:
        row = Setting(key=key, value=value)
        db.session.add(row)
    else:
        row.value = value
    db.session.commit()


def _upload_dir():
    path = os.path.join(current_app.static_folder, 'uploads')
    os.makedirs(path, exist_ok=True)
    return path


def _delete_current_login_bg():
    fname = get_setting('login_bg_filename', '')
    if fname:
        path = os.path.join(_upload_dir(), secure_filename(fname))
        try:
            os.remove(path)
        except OSError:
            pass
