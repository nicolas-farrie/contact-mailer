"""Point d'entrée de l'application Contact Mailer.

Assemble l'application via la factory create_app() : configuration, extensions
(db, login_manager), context_processor global et enregistrement des blueprints
(un module par domaine métier dans blueprints/).

Expose `app` au niveau module pour gunicorn (`app:app`) et les scripts
d'administration (`from app import app, db, init_db`).
"""
from flask import Flask, url_for
from werkzeug.security import generate_password_hash

from models import db, User
from config import Config
from extensions import login_manager
from helpers import get_setting


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


def register_blueprints(app):
    """Enregistre les blueprints : un module par domaine métier."""
    from blueprints.contacts import bp as contacts_bp
    from blueprints.listes import bp as listes_bp
    from blueprints.formulaires import bp as formulaires_bp
    from blueprints.users import bp as users_bp
    from blueprints.imports import bp as imports_bp
    from blueprints.api_integrations import bp as api_integrations_bp
    from blueprints.settings import bp as settings_bp
    from blueprints.public import bp as public_bp
    from blueprints.mailing import bp as mailing_bp

    for bp in (contacts_bp, listes_bp, formulaires_bp, users_bp, imports_bp,
               api_integrations_bp, settings_bp, public_bp, mailing_bp):
        app.register_blueprint(bp)


def register_context_processors(app):
    """Injecte les paramètres d'apparence (nom, fond de login) dans tous les templates."""
    @app.context_processor
    def inject_settings():
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


def create_app(config_object=Config):
    """Factory applicative : configure et assemble l'app Flask."""
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.wsgi_app = ReverseProxied(app.wsgi_app)

    db.init_app(app)
    login_manager.init_app(app)

    register_blueprints(app)
    register_context_processors(app)

    # Registre de champs accessible dans les templates (couche metadata-driven)
    import fields
    app.jinja_env.globals.update(
        fields_group=fields.group,
        field_options=fields.field_options,
        field_def=lambda key: fields.field_map().get(key),
    )

    # Cache-busting des assets statiques : ?v=<mtime> → le navigateur recharge
    # le fichier dès qu'il change (évite un CSS/JS périmé servi depuis le cache).
    import os as _os

    def _asset_version(filename):
        try:
            return int(_os.path.getmtime(_os.path.join(app.static_folder, filename)))
        except OSError:
            return 0
    app.jinja_env.globals['asset_version'] = _asset_version

    return app


app = create_app()


def init_db():
    """Initialise la base et crée l'admin si nécessaire."""
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


init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
