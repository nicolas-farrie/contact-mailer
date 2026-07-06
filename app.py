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
app.register_blueprint(contacts_bp)
app.register_blueprint(listes_bp)
app.register_blueprint(formulaires_bp)
app.register_blueprint(users_bp)
app.register_blueprint(imports_bp)
app.register_blueprint(api_integrations_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(public_bp)


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


# === MAILING ===

@app.route('/mailing')
@login_required
def mailing():
    listes = Liste.query.order_by(Liste.nom).all()
    smtp_configured = bool(Config.SMTP_HOST and Config.SMTP_USER)

    # Pré-remplissage depuis l'historique (réutilisation par campaign_id)
    prefill = {'subject': '', 'body': '', 'format': 'text', 'liste_id': ''}
    from_campaign = request.args.get('from_campaign')
    if from_campaign:
        from mailer import MailQueue
        tpl = MailQueue().get_campaign_template(from_campaign)
        if tpl:
            prefill = {
                'subject': tpl.get('subject', ''),
                'body': tpl.get('body', ''),
                'format': tpl.get('format', 'text'),
                'liste_id': tpl.get('liste_id', ''),
            }

    # Pré-remplissage depuis une demande de diffusion (boîte IMAP)
    # Stocké sur disque (et non en session) car le corps peut contenir des
    # images encodées en base64, trop volumineuses pour un cookie de session.
    submission_attachments = []
    submission_id = None
    from_submission = request.args.get('from_submission')
    if from_submission:
        import json
        from pathlib import Path
        prefill_path = Path(f'data/attachments/submission_{from_submission}/_prefill.json')
        if prefill_path.exists():
            data = json.loads(prefill_path.read_text(encoding='utf-8'))
            prefill = {
                'subject': data.get('subject', ''),
                'body': data.get('body', ''),
                'format': data.get('format', 'text'),
                'liste_id': '',
            }
            submission_attachments = data.get('attachments', [])
            submission_id = from_submission

    return render_template('mailing.html', listes=listes, smtp_configured=smtp_configured, prefill=prefill,
                           submission_attachments=submission_attachments, submission_id=submission_id)


@app.route('/mailing/history')
@login_required
def mailing_history():
    from mailer import MailQueue
    queue = MailQueue()
    campaigns = queue.get_campaigns_list()
    archived = queue.get_archived_campaigns_list()

    bounced_emails = {c.email for c in Contact.query.filter_by(has_bounced=True).all()}
    for c in campaigns + archived:
        c['stats']['bounced'] = len(c['sent_emails'] & bounced_emails)

    return render_template('mailing_history.html', campaigns=campaigns, archived=archived)


@app.route('/mailing/queue/retry/<campaign_id>', methods=['POST'])
@login_required
def mailing_queue_retry(campaign_id):
    from mailer import MailQueue
    queue = MailQueue()
    queue.reset_errors(campaign_id)
    flash('Erreurs remises en attente. Vous pouvez relancer l\'envoi.', 'success')
    return redirect(url_for('mailing_queue', campaign=campaign_id))


@app.route('/mailing/history/archive/<campaign_id>', methods=['POST'])
@login_required
def mailing_history_archive(campaign_id):
    from mailer import MailQueue
    queue = MailQueue()
    queue.archive_campaign(campaign_id)
    flash('Campagne archivée.', 'success')
    return redirect(url_for('mailing_history'))


@app.route('/mailing/history/unarchive/<campaign_id>', methods=['POST'])
@login_required
def mailing_history_unarchive(campaign_id):
    from mailer import MailQueue
    queue = MailQueue()
    queue.unarchive_campaign(campaign_id)
    flash('Campagne restaurée.', 'success')
    return redirect(url_for('mailing_history'))


@app.route('/mailing/history/delete/<campaign_id>', methods=['POST'])
@login_required
@admin_required
def mailing_history_delete(campaign_id):
    from mailer import MailQueue
    queue = MailQueue()
    queue.delete_campaign(campaign_id)
    flash('Campagne supprimée.', 'success')
    return redirect(url_for('mailing_history'))


@app.route('/mailing/submissions')
@login_required
def mailing_submissions():
    """Liste les demandes de diffusion reçues sur la boîte IMAP dédiée"""
    imap_configured = bool(Config.IMAP_HOST and Config.IMAP_USER)
    submissions = []
    error = None

    if imap_configured:
        import imap_submissions
        try:
            submissions = imap_submissions.fetch_submissions(Config)
        except Exception as e:
            error = str(e)

    return render_template('mailing_submissions.html', submissions=submissions,
                           imap_configured=imap_configured, error=error)


@app.route('/mailing/submissions/<uid>/use', methods=['POST'])
@login_required
def mailing_submission_use(uid):
    """Pré-remplit le formulaire mailing depuis une demande.

    Le message n'est marqué comme traité que lorsque le mailing est
    effectivement mis en file d'envoi (cf. mailing_add_to_queue), afin
    qu'une demande abandonnée en cours de route reste visible."""
    import imap_submissions
    from werkzeug.utils import secure_filename
    from pathlib import Path

    try:
        sub = imap_submissions.get_submission(Config, uid)
        if not sub:
            flash('Message introuvable (déjà traité ?)', 'error')
            return redirect(url_for('mailing_submissions'))

        # Sauvegarder les pièces jointes sur disque
        import json
        attach_dir = Path(f'data/attachments/submission_{uid}')
        attach_dir.mkdir(parents=True, exist_ok=True)
        saved_attachments = []
        for a in sub['attachments']:
            filename = secure_filename(a['filename'])
            if filename:
                (attach_dir / filename).write_bytes(a['payload'])
                saved_attachments.append(filename)

        body = sub['body_html'] or sub['body_text']
        fmt = 'html' if sub['body_html'] else 'text'

        # Pré-remplissage stocké sur disque (peut être volumineux : images
        # encodées en base64), pas en session
        prefill_data = {
            'subject': sub['subject'],
            'body': body,
            'format': fmt,
            'attachments': saved_attachments,
        }
        (attach_dir / '_prefill.json').write_text(json.dumps(prefill_data), encoding='utf-8')

        return redirect(url_for('mailing', from_submission=uid))
    except Exception as e:
        flash(f'Erreur lors de la lecture du message : {e}', 'error')
        return redirect(url_for('mailing_submissions'))


@app.route('/mailing/submissions/<uid>/archive', methods=['POST'])
@login_required
def mailing_submission_archive(uid):
    """Archive une demande sans l'utiliser"""
    import imap_submissions
    try:
        imap_submissions.mark_processed(Config, uid)
        flash('Demande archivée.', 'success')
    except Exception as e:
        flash(f'Erreur : {e}', 'error')
    return redirect(url_for('mailing_submissions'))


@app.route('/mailing/submission-attachment/<submission_id>/<filename>')
@login_required
def mailing_submission_attachment(submission_id, filename):
    """Téléchargement d'une pièce jointe extraite d'une demande de diffusion"""
    from pathlib import Path
    attach_dir = Path(f'data/attachments/submission_{submission_id}').absolute()
    return send_from_directory(attach_dir, filename, as_attachment=True)


@app.route('/mailing/preview', methods=['POST'])
@login_required
def mailing_preview():
    """Prévisualisation du mail avec un contact de la liste"""
    liste_id = request.form.get('liste_id', type=int)
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    mail_format = request.form.get('format', 'text')
    include_unsubscribe = request.form.get('include_unsubscribe') == 'on'
    contact_index = request.form.get('contact_index', 0, type=int)

    if not liste_id:
        return jsonify({'error': 'Sélectionnez une liste'}), 400

    liste = Liste.query.get_or_404(liste_id)
    if not liste.active_contacts:
        return jsonify({'error': 'Liste vide'}), 400

    # Sélectionner le contact par index (borné)
    total = len(liste.active_contacts)
    contact_index = max(0, min(contact_index, total - 1))
    contact = liste.active_contacts[contact_index]
    contact_dict = contact.to_dict()

    from mailer import EmailTemplate
    unsub_url = f"{Config.BASE_URL}/unsubscribe/{contact.uid}" if include_unsubscribe else None
    tpl = EmailTemplate(
        subject=subject,
        body_text=body if mail_format == 'text' else '',
        body_html=body if mail_format == 'html' else None,
    )
    preview_subject, preview_body_text, preview_body_html = tpl.render(contact_dict, unsubscribe_url=unsub_url)
    preview_body = preview_body_html if mail_format == 'html' else preview_body_text

    return jsonify({
        'subject': preview_subject,
        'body': preview_body,
        'contact': f"{contact.prenom} {contact.nom} <{contact.email}>",
        'index': contact_index,
        'total': total
    })


@app.route('/mailing/send', methods=['POST'])
@login_required
def mailing_send():
    """Lance l'envoi d'une campagne"""
    from mailer import Mailer, EmailTemplate, MailQueue
    from datetime import datetime

    liste_id = request.form.get('liste_id', type=int)
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()
    mail_format = request.form.get('format', 'text')

    if not all([liste_id, subject, body]):
        flash('Tous les champs sont requis', 'error')
        return redirect(url_for('mailing'))

    if not Config.SMTP_HOST:
        flash('SMTP non configuré', 'error')
        return redirect(url_for('mailing'))

    liste = Liste.query.get_or_404(liste_id)
    if not liste.active_contacts:
        flash('Liste vide', 'error')
        return redirect(url_for('mailing'))

    include_unsubscribe = request.form.get('include_unsubscribe') == 'on'

    # Filtrer les contacts désabonnés
    active_contacts = [c for c in liste.active_contacts if not c.is_unsubscribed]
    excluded = len(liste.active_contacts) - len(active_contacts)
    if excluded:
        flash(f'{excluded} contact{"s" if excluded > 1 else ""} désabonné{"s" if excluded > 1 else ""} exclu{"s" if excluded > 1 else ""} de l\'envoi', 'info')

    if not active_contacts:
        flash('Aucun contact actif dans cette liste (tous désabonnés)', 'error')
        return redirect(url_for('mailing'))

    # Détecter les emails partagés par plusieurs contacts
    email_counts = {}
    for c in active_contacts:
        email_counts[c.email] = email_counts.get(c.email, 0) + 1
    shared_emails = {e: n for e, n in email_counts.items() if n > 1}
    if shared_emails:
        nb = len(shared_emails)
        flash(f'Attention : {nb} adresse{"s" if nb > 1 else ""} partagée{"s" if nb > 1 else ""} '
              f'par plusieurs contacts. Chaque contact recevra son email personnalisé.', 'warning')

    # Préparer les contacts
    contacts = [c.to_dict() for c in active_contacts]

    # Générer un ID de campagne
    campaign_id = f"{liste.nom}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Sauvegarder les pièces jointes sur disque
    from werkzeug.utils import secure_filename
    from pathlib import Path
    import shutil
    attachment_paths = []
    uploaded_files = request.files.getlist('attachments')
    submission_id = request.form.get('submission_id') or None
    # Pièces jointes de la demande explicitement validées par l'utilisateur
    included_submission_attachments = set(request.form.getlist('submission_attachments'))
    if (uploaded_files and uploaded_files[0].filename) or included_submission_attachments:
        attach_dir = Path(f'data/attachments/{campaign_id}')
        attach_dir.mkdir(parents=True, exist_ok=True)
        for f in uploaded_files:
            if f.filename:
                filename = secure_filename(f.filename)
                if filename:
                    filepath = attach_dir / filename
                    f.save(str(filepath))
                    attachment_paths.append(str(filepath))

        # Reprendre les pièces jointes de la demande de diffusion validées par l'utilisateur
        if submission_id and included_submission_attachments:
            submission_dir = Path(f'data/attachments/submission_{submission_id}')
            if submission_dir.is_dir():
                for f in submission_dir.iterdir():
                    if f.is_file() and f.name in included_submission_attachments:
                        dest = attach_dir / f.name
                        shutil.copy(str(f), str(dest))
                        attachment_paths.append(str(dest))

    # Sauvegarder le template (sans encore peupler la queue)
    queue = MailQueue()
    queue.set_campaign_template(campaign_id, subject, body, mail_format,
                                sent_by=current_user.username,
                                include_unsubscribe=include_unsubscribe,
                                attachments=attachment_paths or None,
                                liste_id=liste_id,
                                submission_id=submission_id)

    return redirect(url_for('mailing_confirm', campaign=campaign_id))


@app.route('/mailing/confirm')
@login_required
def mailing_confirm():
    """Page de confirmation : sélection des contacts avant mise en file"""
    from mailer import MailQueue
    campaign_id = request.args.get('campaign')
    if not campaign_id:
        return redirect(url_for('mailing'))

    queue = MailQueue()
    tpl = queue.get_campaign_template(campaign_id)
    if not tpl:
        flash('Campagne introuvable', 'error')
        return redirect(url_for('mailing'))

    liste_id = tpl.get('liste_id')
    liste = Liste.query.get_or_404(liste_id)
    active_contacts = [c for c in liste.active_contacts if not c.is_unsubscribed]

    return render_template('mailing_confirm.html',
                           campaign_id=campaign_id,
                           template=tpl,
                           liste=liste,
                           contacts=active_contacts)


@app.route('/mailing/add-to-queue', methods=['POST'])
@login_required
def mailing_add_to_queue():
    """Ajoute les contacts sélectionnés à la file d'envoi"""
    from mailer import MailQueue
    campaign_id = request.form.get('campaign_id')
    contact_ids = set(request.form.getlist('contact_ids', type=int))

    if not campaign_id or not contact_ids:
        flash('Aucun contact sélectionné', 'error')
        return redirect(url_for('mailing'))

    queue = MailQueue()
    tpl = queue.get_campaign_template(campaign_id)
    liste_id = tpl.get('liste_id')
    liste = Liste.query.get_or_404(liste_id)

    selected = [c for c in liste.active_contacts if c.id in contact_ids and not c.is_unsubscribed]
    for contact in selected:
        queue.add(contact.to_dict(), campaign_id)

    # Si ce mailing provient d'une demande de diffusion, on la marque traitée
    # maintenant qu'elle a réellement été mise en file d'envoi
    submission_id = tpl.get('submission_id')
    if submission_id:
        import imap_submissions
        import shutil
        try:
            imap_submissions.mark_processed(Config, submission_id)
        except Exception as e:
            flash(f'Campagne créée, mais erreur lors du classement de la demande : {e}', 'error')
        shutil.rmtree(f'data/attachments/submission_{submission_id}', ignore_errors=True)

    flash(f'Campagne "{campaign_id}" créée avec {len(selected)} contacts.', 'success')
    return redirect(url_for('mailing_queue', campaign=campaign_id))


@app.route('/mailing/queue')
@login_required
def mailing_queue():
    """Affiche la file d'attente"""
    from mailer import MailQueue

    campaign = request.args.get('campaign')
    queue = MailQueue()
    stats = queue.get_stats(campaign)
    template = queue.get_campaign_template(campaign) if campaign else {}

    # Récupérer les items de la file
    items = queue.queue
    if campaign:
        items = [i for i in items if i['campaign_id'] == campaign]

    return render_template('mailing_queue.html', items=items, stats=stats,
                           campaign=campaign, template=template)


@app.route('/mailing/process', methods=['POST'])
@login_required
def mailing_process():
    """Traite la file d'attente (envoie les emails en attente)"""
    from mailer import Mailer, EmailTemplate, MailQueue

    campaign = request.form.get('campaign')

    if not Config.SMTP_HOST:
        flash('SMTP non configuré', 'error')
        return redirect(url_for('mailing'))

    queue = MailQueue()
    pending = queue.get_pending(campaign)

    if not pending:
        flash('Aucun email en attente', 'info')
        return redirect(url_for('mailing_queue', campaign=campaign))

    # Récupérer le template sauvegardé avec la campagne
    tpl = queue.get_campaign_template(campaign)
    if not tpl:
        flash('Template de campagne introuvable', 'error')
        return redirect(url_for('mailing_queue', campaign=campaign))

    # Créer le mailer
    mailer = Mailer(
        smtp_host=Config.SMTP_HOST,
        smtp_port=Config.SMTP_PORT,
        smtp_user=Config.SMTP_USER,
        smtp_password=Config.SMTP_PASSWORD,
        sender_email=Config.SMTP_SENDER_EMAIL,
        sender_name=Config.SMTP_SENDER_NAME,
        use_tls=Config.SMTP_USE_TLS
    )

    mail_format = tpl.get('format', 'text')
    include_unsubscribe = tpl.get('include_unsubscribe', False)
    attachments = tpl.get('attachments', [])

    if mail_format == 'html':
        template = EmailTemplate(subject=tpl['subject'], body_text='', body_html=tpl['body'])
    else:
        template = EmailTemplate(subject=tpl['subject'], body_text=tpl['body'])

    delay = 60.0 / Config.MAIL_RATE_PER_MINUTE
    sent = 0
    errors = 0

    import time
    for item in pending:
        contact = item['contact']

        # Construire l'URL de désabonnement par contact
        unsub_url = None
        if include_unsubscribe and contact.get('uid'):
            unsub_url = f"{Config.BASE_URL}/unsubscribe/{contact['uid']}"

        try:
            subj, body_text, body_html = template.render(contact, unsubscribe_url=unsub_url)
            return_path = Config.BOUNCE_RETURN_PATH or Config.BOUNCE_IMAP_USER or None
            mailer.send_single(contact['email'], subj, body_text, body_html,
                               unsubscribe_url=unsub_url, attachments=attachments,
                               return_path=return_path)
            queue.mark_sent(item['id'])
            sent += 1
        except Exception as e:
            queue.mark_error(item['id'], str(e))
            errors += 1
        time.sleep(delay)

    # Envoyer une copie récapitulative à l'expéditeur
    try:
        first_contact = pending[0]['contact']
        subj, body_text, body_html = template.render(first_contact)
        copy_subject = f"[Campagne {campaign} — {sent} envoyés, {errors} erreurs] {subj}"

        # Récapitulatif des résultats à ajouter au corps
        recap_text = (
            f"\n\n{'='*60}\n"
            f"RÉCAPITULATIF CAMPAGNE : {campaign}\n"
            f"{'='*60}\n"
            f"  Envoyés  : {sent}\n"
            f"  Erreurs  : {errors}\n"
            f"  Total    : {len(pending)}\n"
        )
        if errors > 0:
            failed = [i['contact']['email'] for i in pending if i['status'] == 'error']
            recap_text += f"\nEmails en erreur :\n" + "\n".join(f"  - {e}" for e in failed) + "\n"
        if attachments:
            recap_text += f"\nPièces jointes : {', '.join(Path(p).name for p in attachments)}\n"
        recap_text += f"{'='*60}\n"

        recap_html = (
            f'<hr><div style="font-family:monospace;font-size:13px;color:#555;background:#f5f5f5;padding:1rem;border-radius:4px;">'
            f'<strong>Récapitulatif — {campaign}</strong><br><br>'
            f'Envoyés : <strong>{sent}</strong> &nbsp;|&nbsp; '
            f'Erreurs : <strong style="color:{"#c00" if errors else "#090"}">{errors}</strong> &nbsp;|&nbsp; '
            f'Total : <strong>{len(pending)}</strong>'
        )
        if errors > 0:
            failed = [i['contact']['email'] for i in pending if i['status'] == 'error']
            recap_html += '<br><br>Emails en erreur :<br>' + '<br>'.join(f'&nbsp;• {e}' for e in failed)
        if attachments:
            recap_html += f'<br><br>Pièces jointes : {", ".join(Path(p).name for p in attachments)}'
        recap_html += '</div>'

        copy_body_text = body_text + recap_text
        copy_body_html = (body_html + recap_html) if body_html else None

        mailer.send_single(Config.SMTP_SENDER_EMAIL, copy_subject,
                           copy_body_text, copy_body_html, attachments=attachments)
    except Exception as e:
        flash(f'Copie expéditeur non envoyée : {e}', 'warning')

    flash(f'Envoi terminé : {sent} envoyés, {errors} erreurs', 'success' if errors == 0 else 'warning')
    return redirect(url_for('mailing_queue', campaign=campaign))


@app.route('/mailing/test-smtp', methods=['POST'])
@login_required
def mailing_test_smtp():
    """Test la connexion SMTP"""
    import smtplib
    import ssl

    if not Config.SMTP_HOST:
        return jsonify({'success': False, 'error': 'SMTP non configuré'})

    try:
        context = ssl.create_default_context()
        if Config.SMTP_USE_TLS:
            with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
                server.starttls(context=context)
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        else:
            with smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, context=context) as server:
                server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


# === DESABONNEMENT ===

init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
