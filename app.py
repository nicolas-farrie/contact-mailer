from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Contact, Liste, User
from config import Config
import csv
import io
from vcard_converter import extract_vcard_data, get_vcards, MULTI_VALUE_SEP

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Veuillez vous connecter.'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def init_db():
    """Initialise la base et crée l'admin si nécessaire"""
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username=Config.ADMIN_USERNAME).first():
            admin = User(
                username=Config.ADMIN_USERNAME,
                password_hash=generate_password_hash(Config.ADMIN_PASSWORD)
            )
            db.session.add(admin)
            db.session.commit()


# === AUTHENTIFICATION ===

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('contacts'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('contacts'))
        flash('Identifiants incorrects', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# === CONTACTS ===

@app.route('/')
@app.route('/contacts')
@login_required
def contacts():
    liste_filter = request.args.get('liste', type=int)
    search = request.args.get('q', '').strip()

    query = Contact.query

    if liste_filter:
        liste = Liste.query.get(liste_filter)
        if liste:
            query = query.filter(Contact.listes.contains(liste))

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Contact.nom.ilike(search_pattern),
                Contact.prenom.ilike(search_pattern),
                Contact.email.ilike(search_pattern),
                Contact.organisation.ilike(search_pattern)
            )
        )

    contacts_list = query.order_by(Contact.nom, Contact.prenom).all()
    listes = Liste.query.order_by(Liste.nom).all()

    return render_template('contacts.html',
                           contacts=contacts_list,
                           listes=listes,
                           liste_filter=liste_filter,
                           search=search)


@app.route('/contacts/new', methods=['GET', 'POST'])
@login_required
def contact_new():
    if request.method == 'POST':
        contact = Contact(
            nom=request.form.get('nom', '').strip(),
            prenom=request.form.get('prenom', '').strip(),
            email=request.form.get('email', '').strip(),
            telephone=request.form.get('telephone', '').strip(),
            organisation=request.form.get('organisation', '').strip(),
            notes=request.form.get('notes', '').strip()
        )

        # Ajouter aux listes sélectionnées
        liste_ids = request.form.getlist('listes')
        for lid in liste_ids:
            liste = Liste.query.get(int(lid))
            if liste:
                contact.listes.append(liste)

        db.session.add(contact)
        try:
            db.session.commit()
            flash(f'Contact {contact.prenom} {contact.nom} créé', 'success')
            return redirect(url_for('contacts'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    listes = Liste.query.order_by(Liste.nom).all()
    return render_template('contact_form.html', contact=None, listes=listes)


@app.route('/contacts/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def contact_edit(id):
    contact = Contact.query.get_or_404(id)

    if request.method == 'POST':
        contact.nom = request.form.get('nom', '').strip()
        contact.prenom = request.form.get('prenom', '').strip()
        contact.email = request.form.get('email', '').strip()
        contact.telephone = request.form.get('telephone', '').strip()
        contact.organisation = request.form.get('organisation', '').strip()
        contact.notes = request.form.get('notes', '').strip()

        # Mettre à jour les listes
        contact.listes.clear()
        liste_ids = request.form.getlist('listes')
        for lid in liste_ids:
            liste = Liste.query.get(int(lid))
            if liste:
                contact.listes.append(liste)

        try:
            db.session.commit()
            flash(f'Contact mis à jour', 'success')
            return redirect(url_for('contacts'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    listes = Liste.query.order_by(Liste.nom).all()
    return render_template('contact_form.html', contact=contact, listes=listes)


@app.route('/contacts/<int:id>/delete', methods=['POST'])
@login_required
def contact_delete(id):
    contact = Contact.query.get_or_404(id)
    nom_complet = f'{contact.prenom} {contact.nom}'
    db.session.delete(contact)
    db.session.commit()
    flash(f'Contact {nom_complet} supprimé', 'success')
    return redirect(url_for('contacts'))


# === LISTES ===

@app.route('/listes')
@login_required
def listes():
    listes_list = Liste.query.order_by(Liste.nom).all()
    return render_template('listes.html', listes=listes_list)


@app.route('/listes/new', methods=['GET', 'POST'])
@login_required
def liste_new():
    if request.method == 'POST':
        liste = Liste(
            nom=request.form.get('nom', '').strip(),
            description=request.form.get('description', '').strip()
        )
        db.session.add(liste)
        try:
            db.session.commit()
            flash(f'Liste "{liste.nom}" créée', 'success')
            return redirect(url_for('listes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    return render_template('liste_form.html', liste=None)


@app.route('/listes/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def liste_edit(id):
    liste = Liste.query.get_or_404(id)

    if request.method == 'POST':
        liste.nom = request.form.get('nom', '').strip()
        liste.description = request.form.get('description', '').strip()
        try:
            db.session.commit()
            flash(f'Liste mise à jour', 'success')
            return redirect(url_for('listes'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    return render_template('liste_form.html', liste=liste)


@app.route('/listes/<int:id>/delete', methods=['POST'])
@login_required
def liste_delete(id):
    liste = Liste.query.get_or_404(id)
    nom = liste.nom
    db.session.delete(liste)
    db.session.commit()
    flash(f'Liste "{nom}" supprimée', 'success')
    return redirect(url_for('listes'))


# === ACTIONS EN MASSE ===

@app.route('/contacts/bulk-action', methods=['POST'])
@login_required
def contacts_bulk_action():
    action = request.form.get('action')
    contact_ids = request.form.getlist('contact_ids')
    liste_id = request.form.get('liste_id', type=int)

    if not contact_ids:
        flash('Aucun contact sélectionné', 'error')
        return redirect(url_for('contacts'))

    contacts = Contact.query.filter(Contact.id.in_(contact_ids)).all()
    liste = Liste.query.get(liste_id) if liste_id else None

    if action == 'add_to_liste' and liste:
        for contact in contacts:
            if liste not in contact.listes:
                contact.listes.append(liste)
        db.session.commit()
        flash(f'{len(contacts)} contacts ajoutés à "{liste.nom}"', 'success')

    elif action == 'remove_from_liste' and liste:
        for contact in contacts:
            if liste in contact.listes:
                contact.listes.remove(liste)
        db.session.commit()
        flash(f'{len(contacts)} contacts retirés de "{liste.nom}"', 'success')

    elif action == 'delete':
        for contact in contacts:
            db.session.delete(contact)
        db.session.commit()
        flash(f'{len(contacts)} contacts supprimés', 'success')

    return redirect(url_for('contacts'))


# === IMPORT / EXPORT ===

def _parse_liste_names(raw):
    """Parse les noms de listes depuis une chaîne (vCard: 'Catégories', TSV: 'Listes')."""
    if not raw:
        return []
    raw = raw.strip().replace('[', '').replace(']', '').replace("'", '')
    for sep in [MULTI_VALUE_SEP.strip(), ',']:
        if sep in raw:
            return [c.strip() for c in raw.split(sep) if c.strip()]
    return [raw.strip()] if raw.strip() else []


def _extract_fields_from_row(row):
    """Extrait les champs normalisés depuis un dict (TSV ou vCard).

    Accepte les colonnes 'Listes', 'Catégories' ou 'Categories' pour les listes
    (rétrocompatibilité vCard et TSV).
    """
    # Email
    email_val = (
        row.get('Email', '') or
        row.get('email', '') or
        row.get('Email_Home', '') or
        row.get('Email_Work', '') or
        row.get('Email_Autre', '')
    ).strip()
    if MULTI_VALUE_SEP.strip() in email_val:
        email_val = email_val.split(MULTI_VALUE_SEP.strip())[0].strip()

    # Nom / Prénom
    nom = ''
    prenom = ''
    nom_prenom = row.get('Nom, Prénom', '')
    if nom_prenom:
        parts = nom_prenom.split(',', 1)
        nom = parts[0].strip()
        prenom = parts[1].strip() if len(parts) > 1 else ''

    if not nom:
        nom = row.get('Nom', row.get('nom', '')).strip()
    if not prenom:
        prenom = row.get('Prenom', row.get('prenom', row.get('Prénom', ''))).strip()

    if not nom and not prenom:
        fn = row.get('Nom Complet', '').strip()
        if fn:
            parts = fn.rsplit(' ', 1)
            if len(parts) == 2:
                prenom, nom = parts
            else:
                nom = fn

    # Téléphone
    telephone = (
        row.get('Tel_Cell', '') or
        row.get('Tel_Home', '') or
        row.get('Tel_Work', '') or
        row.get('telephone', '') or
        row.get('Tel', '')
    ).strip()
    if MULTI_VALUE_SEP.strip() in telephone:
        telephone = telephone.split(MULTI_VALUE_SEP.strip())[0].strip()

    # Listes (accepte 'Listes', 'Catégories', 'Categories' pour rétrocompatibilité)
    listes_raw = (
        row.get('Listes', '') or
        row.get('Catégories', '') or
        row.get('Categories', '')
    )
    listes = _parse_liste_names(listes_raw)

    return {
        'email': email_val,
        'nom': nom,
        'prenom': prenom,
        'telephone': telephone,
        'organisation': row.get('Organisation', row.get('organisation', '')).strip(),
        'notes': row.get('Note', row.get('Notes', row.get('notes', ''))).strip(),
        'listes': listes,
    }


def _get_or_create_listes(noms):
    """Retourne les objets Liste pour une liste de noms, en créant ceux qui n'existent pas."""
    listes = []
    for nom in noms:
        liste = Liste.query.filter_by(nom=nom).first()
        if not liste:
            liste = Liste(nom=nom)
            db.session.add(liste)
        listes.append(liste)
    return listes


def _import_contact_from_row(row, update_existing=False):
    """
    Importe un contact depuis un dict (TSV ou vCard).
    Retourne (contact, action) où action = 'created', 'updated', 'no_email' ou 'skipped'.
    """
    fields = _extract_fields_from_row(row)

    if not fields['email']:
        return None, 'no_email'

    existing = Contact.query.filter_by(email=fields['email']).first()

    if existing and not update_existing:
        return None, 'skipped'

    if existing and update_existing:
        # Mettre à jour les champs non vides
        if fields['nom']:
            existing.nom = fields['nom']
        if fields['prenom']:
            existing.prenom = fields['prenom']
        if fields['telephone']:
            existing.telephone = fields['telephone']
        if fields['organisation']:
            existing.organisation = fields['organisation']
        if fields['notes']:
            existing.notes = fields['notes']

        # Remplacement des listes par celles de l'import
        if fields['listes']:
            existing.listes = _get_or_create_listes(fields['listes'])

        return existing, 'updated'

    # Nouveau contact
    contact = Contact(
        nom=fields['nom'],
        prenom=fields['prenom'],
        email=fields['email'],
        telephone=fields['telephone'],
        organisation=fields['organisation'],
        notes=fields['notes']
    )
    contact.listes = _get_or_create_listes(fields['listes'])

    return contact, 'created'


@app.route('/import', methods=['GET', 'POST'])
@login_required
def import_contacts():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('Aucun fichier sélectionné', 'error')
            return redirect(url_for('import_contacts'))

        update_existing = request.form.get('update_existing') == 'on'
        filename = file.filename.lower()
        created = 0
        updated = 0
        skipped = 0
        no_email = 0

        try:
            rows = []

            if filename.endswith('.vcf') or filename.endswith('.vcard'):
                # === IMPORT VCARD ===
                import tempfile
                content = file.read()
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.vcf', mode='wb')
                tmp.write(content)
                tmp.close()

                for vcard in get_vcards(tmp.name):
                    rows.append(extract_vcard_data(vcard, tmp.name))

                import os
                os.unlink(tmp.name)

            else:
                # === IMPORT TSV/CSV ===
                content = file.read().decode('utf-8')
                first_line = content.split('\n')[0]
                delimiter = '\t' if '\t' in first_line else ','
                reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
                rows = list(reader)

            for row in rows:
                contact, action = _import_contact_from_row(row, update_existing=update_existing)
                if action == 'created':
                    db.session.add(contact)
                    created += 1
                elif action == 'updated':
                    updated += 1
                elif action == 'skipped':
                    skipped += 1
                else:
                    no_email += 1

            db.session.commit()

            parts = []
            if created:
                parts.append(f'{created} créés')
            if updated:
                parts.append(f'{updated} mis à jour')
            if skipped:
                parts.append(f'{skipped} inchangés')
            if no_email:
                parts.append(f'{no_email} sans email ignorés')
            flash('Import : ' + ', '.join(parts), 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Erreur import: {e}', 'error')

        return redirect(url_for('contacts'))

    return render_template('import.html')


@app.route('/export')
@login_required
def export_contacts():
    liste_id = request.args.get('liste', type=int)

    if liste_id:
        liste = Liste.query.get_or_404(liste_id)
        contacts = liste.contacts
        filename = f'contacts_{liste.nom}.tsv'
    else:
        contacts = Contact.query.order_by(Contact.nom, Contact.prenom).all()
        filename = 'contacts_all.tsv'

    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t')
    writer.writerow(['Nom', 'Prenom', 'Email', 'Telephone', 'Organisation', 'Notes', 'Listes'])

    for c in contacts:
        writer.writerow([
            c.nom, c.prenom, c.email, c.telephone or '',
            c.organisation or '', c.notes or '',
            ','.join([l.nom for l in c.listes])
        ])

    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/tab-separated-values',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# === MAILING ===

@app.route('/mailing')
@login_required
def mailing():
    listes = Liste.query.order_by(Liste.nom).all()
    smtp_configured = bool(Config.SMTP_HOST and Config.SMTP_USER)

    # Pré-remplissage depuis l'historique (réutilisation)
    prefill = {
        'subject': request.args.get('subject', ''),
        'body': request.args.get('body', ''),
        'format': request.args.get('format', 'text'),
    }

    return render_template('mailing.html', listes=listes, smtp_configured=smtp_configured, prefill=prefill)


@app.route('/mailing/history')
@login_required
def mailing_history():
    """Affiche l'historique des campagnes envoyées"""
    from mailer import MailQueue

    queue = MailQueue()
    campaigns = queue.get_campaigns_list()

    return render_template('mailing_history.html', campaigns=campaigns)


@app.route('/mailing/preview', methods=['POST'])
@login_required
def mailing_preview():
    """Prévisualisation du mail avec le premier contact de la liste"""
    liste_id = request.form.get('liste_id', type=int)
    subject = request.form.get('subject', '').strip()
    body = request.form.get('body', '').strip()

    if not liste_id:
        return jsonify({'error': 'Sélectionnez une liste'}), 400

    liste = Liste.query.get_or_404(liste_id)
    if not liste.contacts:
        return jsonify({'error': 'Liste vide'}), 400

    # Prendre le premier contact pour la preview
    contact = liste.contacts[0]
    contact_dict = contact.to_dict()

    # Remplacer les variables
    preview_subject = subject
    preview_body = body
    for key, value in contact_dict.items():
        preview_subject = preview_subject.replace(f'{{{key}}}', str(value or ''))
        preview_body = preview_body.replace(f'{{{key}}}', str(value or ''))

    return jsonify({
        'subject': preview_subject,
        'body': preview_body,
        'contact': f"{contact.prenom} {contact.nom} <{contact.email}>"
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
    if not liste.contacts:
        flash('Liste vide', 'error')
        return redirect(url_for('mailing'))

    # Préparer les contacts
    contacts = [c.to_dict() for c in liste.contacts]

    # Générer un ID de campagne
    campaign_id = f"{liste.nom}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Ajouter à la file d'attente et sauvegarder le template
    queue = MailQueue()
    queue.set_campaign_template(campaign_id, subject, body, mail_format)
    for contact in contacts:
        queue.add(contact, campaign_id)

    flash(f'Campagne "{campaign_id}" créée avec {len(contacts)} contacts.', 'success')
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
        try:
            subj, body_text, body_html = template.render(contact)
            mailer.send_single(contact['email'], subj, body_text, body_html)
            queue.mark_sent(item['id'])
            sent += 1
        except Exception as e:
            queue.mark_error(item['id'], str(e))
            errors += 1
        time.sleep(delay)

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


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
