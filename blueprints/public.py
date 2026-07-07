"""Blueprint public : pages sans authentification (login, logout, désabonnement,
mot de passe oublié) et ressources PWA (manifest, icône générée).

Endpoints : public.login, public.logout, public.unsubscribe,
public.forgot_password, public.pwa_manifest, public.pwa_icon.
"""
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, Response, current_app)
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash

from models import db, User, Contact
from config import Config

bp = Blueprint('public', __name__)


# === PWA MANIFEST ===

@bp.route('/manifest.json')
def pwa_manifest():
    instance_name = current_app.config.get('INSTANCE_NAME')
    name = instance_name or 'Contact Mailer'
    color = current_app.config.get('INSTANCE_COLOR', '#579d48')
    if instance_name:
        icons = [
            {'src': url_for('public.pwa_icon', size=192), 'sizes': '192x192', 'type': 'image/svg+xml'},
            {'src': url_for('public.pwa_icon', size=512), 'sizes': '512x512', 'type': 'image/svg+xml'},
        ]
    else:
        icons = [
            {'src': url_for('static', filename='contact-mailer.png'), 'sizes': '512x512', 'type': 'image/png'},
        ]
    manifest = {
        'name': name,
        'short_name': name,
        'start_url': '/',
        'display': 'standalone',
        'background_color': color,
        'theme_color': color,
        'icons': icons,
    }
    return jsonify(manifest)


@bp.route('/icon-<int:size>.svg')
def pwa_icon(size):
    name = current_app.config.get('INSTANCE_NAME') or 'CM'
    color = current_app.config.get('INSTANCE_COLOR', '#2563eb')
    words = name.split()
    initials = (words[0][0] + words[1][0]).upper() if len(words) >= 2 else name[:2].upper()
    font_size = size * 0.38
    cx = size / 2
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 {size} {size}">
  <rect width="{size}" height="{size}" rx="{size * 0.18}" fill="{color}"/>
  <text x="{cx}" y="{cx}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif"
        font-size="{font_size}" font-weight="600" fill="white"
        text-anchor="middle" dominant-baseline="central">{initials}</text>
</svg>'''
    return Response(svg, mimetype='image/svg+xml')


# === AUTHENTIFICATION ===

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('contacts.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            if not user.is_active:
                flash('Ce compte a été désactivé. Contactez un administrateur.', 'error')
                return render_template('login.html')
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('contacts.index'))
        flash('Identifiants incorrects', 'error')

    return render_template('login.html')


@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('public.login'))


# === DESABONNEMENT ===

@bp.route('/unsubscribe/<uid>', methods=['GET', 'POST'])
def unsubscribe(uid):
    """Page publique de désabonnement (pas de login_required)"""
    from datetime import datetime

    contact = Contact.query.filter_by(uid=uid).first()

    if not contact:
        return render_template('unsubscribe.html', state='invalid')

    if contact.is_unsubscribed:
        return render_template('unsubscribe.html', state='already')

    if request.method == 'POST':
        contact.is_unsubscribed = True
        contact.unsubscribed_at = datetime.utcnow()
        db.session.commit()
        return render_template('unsubscribe.html', state='done')

    # GET : page de confirmation avec bouton
    return render_template('unsubscribe.html', state='confirm', uid=uid)


# === MOT DE PASSE OUBLIE ===

@bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Page publique : notifie l'admin qu'un utilisateur a oublié son mot de passe."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        if username:
            instance_name = Config.INSTANCE_NAME or 'Contact Mailer'
            # Envoyer un email de notification à l'admin
            if Config.SMTP_HOST and Config.SMTP_SENDER_EMAIL:
                try:
                    import smtplib
                    import ssl
                    from email.mime.text import MIMEText
                    from email.utils import formataddr, formatdate

                    body = (
                        f"L'utilisateur « {username} » a demandé une réinitialisation "
                        f"de mot de passe pour l'instance « {instance_name} ».\n\n"
                        f"Si cette demande est légitime, connectez-vous en tant qu'admin "
                        f"et modifiez le mot de passe de cet utilisateur."
                    )
                    msg = MIMEText(body, 'plain', 'utf-8')
                    msg['Subject'] = f"[{instance_name}] Mot de passe oublié — {username}"
                    msg['From'] = formataddr((Config.SMTP_SENDER_NAME, Config.SMTP_SENDER_EMAIL))
                    msg['To'] = Config.SMTP_SENDER_EMAIL
                    msg['Date'] = formatdate(localtime=True)

                    context = ssl.create_default_context()
                    if Config.SMTP_USE_TLS:
                        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                            server.starttls(context=context)
                            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                            server.sendmail(Config.SMTP_SENDER_EMAIL, Config.SMTP_SENDER_EMAIL, msg.as_string())
                    else:
                        with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, context=context) as server:
                            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
                            server.sendmail(Config.SMTP_SENDER_EMAIL, Config.SMTP_SENDER_EMAIL, msg.as_string())
                except Exception:
                    pass  # Ne pas révéler si l'envoi a échoué

        # Message identique que le user existe ou non (sécurité)
        flash('Si ce compte existe, l\'administrateur a été notifié. Il vous contactera pour réinitialiser votre mot de passe.', 'success')
        return redirect(url_for('public.forgot_password'))

    return render_template('forgot_password.html')
