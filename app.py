from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory, Response
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Contact, Liste, User, BookstackRole, Setting, PreferenceForm, PreferenceFormListe, PreferenceResponse
from config import Config
import csv
import io
import os
from datetime import datetime
import uuid
from werkzeug.utils import secure_filename
from vcard_converter import extract_vcard_data, get_vcards, MULTI_VALUE_SEP

from extensions import login_manager
from helpers import (
    admin_required,
    get_setting, set_setting, _upload_dir, _delete_current_login_bg,
    SETTING_DEFAULTS, ALLOWED_IMAGE_EXT, MAX_IMAGE_BYTES,
)


class ReverseProxied:
    """Middleware WSGI pour supporter un préfixe de chemin (reverse proxy par sous-répertoire).
    Lit le header X-Script-Name posé par nginx et ajuste SCRIPT_NAME / PATH_INFO."""
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        script_name = environ.get('HTTP_X_SCRIPT_NAME', '')
        if script_name:
            environ['SCRIPT_NAME'] = script_name
            path_info = environ.get('PATH_INFO', '')
            if path_info.startswith(script_name):
                environ['PATH_INFO'] = path_info[len(script_name):]
        return self.app(environ, start_response)


app = Flask(__name__)
app.config.from_object(Config)
app.wsgi_app = ReverseProxied(app.wsgi_app)

db.init_app(app)
login_manager.init_app(app)


# === BLUEPRINTS ===
# Enregistrés au fur et à mesure de la modularisation de app.py.
from blueprints.contacts import bp as contacts_bp
from blueprints.listes import bp as listes_bp
from blueprints.formulaires import bp as formulaires_bp
from blueprints.users import bp as users_bp
from blueprints.imports import bp as imports_bp
from blueprints.api_integrations import bp as api_integrations_bp
from blueprints.settings import bp as settings_bp
from blueprints.public import bp as public_bp
from blueprints.mailing import bp as mailing_bp
app.register_blueprint(contacts_bp)
app.register_blueprint(listes_bp)
app.register_blueprint(formulaires_bp)
app.register_blueprint(users_bp)
app.register_blueprint(imports_bp)
app.register_blueprint(api_integrations_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(public_bp)
app.register_blueprint(mailing_bp)


def init_db():
    """Initialise la base et crée l'admin si nécessaire"""
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username=Config.ADMIN_USERNAME).first():
            admin = User(
                username=Config.ADMIN_USERNAME,
                password_hash=generate_password_hash(Config.ADMIN_PASSWORD),
                role='admin',
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()


# === PARAMÈTRES APPLICATIFS ===
# get_setting / set_setting / _upload_dir / _delete_current_login_bg et les
# constantes SETTING_DEFAULTS / ALLOWED_IMAGE_EXT / MAX_IMAGE_BYTES vivent
# désormais dans helpers.py (importés en tête de fichier).


@app.context_processor
def inject_settings():
    with app.app_context():
        try:
            fname = get_setting('login_bg_filename', '')
            login_bg_url = url_for('static', filename=f'uploads/{fname}') if fname else None
            try:
                overlay = float(get_setting('login_overlay', '0.35'))
            except (TypeError, ValueError):
                overlay = 0.35
            return {
                'app_name': get_setting('app_name', 'Contact Mailer'),
                'login_bg_url': login_bg_url,
                'login_overlay': overlay,
            }
        except Exception:
            return {'app_name': 'Contact Mailer', 'login_bg_url': None, 'login_overlay': 0.35}


init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
