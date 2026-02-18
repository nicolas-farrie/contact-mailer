from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, Contact, Liste, User, BookstackRole
from config import Config
import csv
import io
from vcard_converter import extract_vcard_data, get_vcards, MULTI_VALUE_SEP


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
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Veuillez vous connecter.'


@login_manager.user_loader
def load_user(user_id):
    user = User.query.get(int(user_id))
    if user and not user.is_active:
        return None
    return user


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            flash('Accès réservé aux administrateurs', 'error')
            return redirect(url_for('contacts'))
        return f(*args, **kwargs)
    return decorated


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
            if not user.is_active:
                flash('Ce compte a été désactivé. Contactez un administrateur.', 'error')
                return render_template('login.html')
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
    source_filter = request.args.get('source', '').strip()
    search = request.args.get('q', '').strip()

    query = Contact.query

    if liste_filter:
        liste = Liste.query.get(liste_filter)
        if liste:
            query = query.filter(Contact.listes.contains(liste))

    if source_filter:
        query = query.filter(Contact.source == source_filter)

    if search:
        search_pattern = f'%{search}%'
        query = query.filter(
            db.or_(
                Contact.nom.ilike(search_pattern),
                Contact.prenom.ilike(search_pattern),
                Contact.email.ilike(search_pattern),
                Contact.organisation.ilike(search_pattern),
                Contact.adresse_ville.ilike(search_pattern)
            )
        )

    contacts_list = query.order_by(Contact.nom, Contact.prenom).all()
    listes = Liste.query.order_by(Liste.nom).all()
    # Sources distinctes pour le filtre
    sources = db.session.query(Contact.source).distinct().order_by(Contact.source).all()
    sources = [s[0] for s in sources if s[0]]

    return render_template('contacts.html',
                           contacts=contacts_list,
                           listes=listes,
                           sources=sources,
                           liste_filter=liste_filter,
                           source_filter=source_filter,
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
            adresse_rue=request.form.get('adresse_rue', '').strip(),
            adresse_complement=request.form.get('adresse_complement', '').strip(),
            adresse_ville=request.form.get('adresse_ville', '').strip(),
            adresse_cp=request.form.get('adresse_cp', '').strip(),
            adresse_region=request.form.get('adresse_region', '').strip(),
            adresse_pays=request.form.get('adresse_pays', '').strip(),
            notes=request.form.get('notes', '').strip(),
            source='Manuel',
            created_by_id=current_user.id
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
        contact.adresse_rue = request.form.get('adresse_rue', '').strip()
        contact.adresse_complement = request.form.get('adresse_complement', '').strip()
        contact.adresse_ville = request.form.get('adresse_ville', '').strip()
        contact.adresse_cp = request.form.get('adresse_cp', '').strip()
        contact.adresse_region = request.form.get('adresse_region', '').strip()
        contact.adresse_pays = request.form.get('adresse_pays', '').strip()
        contact.notes = request.form.get('notes', '').strip()
        contact.updated_by_id = current_user.id

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
        'uid': row.get('UID', row.get('uid', '')).strip(),
        'email': email_val,
        'nom': nom,
        'prenom': prenom,
        'telephone': telephone,
        'organisation': row.get('Organisation', row.get('organisation', '')).strip(),
        'adresse_rue': row.get('Rue', row.get('adresse_rue', '')).strip(),
        'adresse_complement': row.get('Complement', row.get('adresse_complement', '')).strip(),
        'adresse_ville': row.get('Ville', row.get('adresse_ville', '')).strip(),
        'adresse_cp': row.get('CP', row.get('adresse_cp', '')).strip(),
        'adresse_region': row.get('Region', row.get('adresse_region', '')).strip(),
        'adresse_pays': row.get('Pays', row.get('adresse_pays', '')).strip(),
        'source': row.get('Source', row.get('source', '')).strip(),
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


def _detect_vcard_source(content):
    """Détecte la source d'un fichier vCard depuis son contenu (PRODID, format UID)."""
    content_lower = content.lower()
    if 'prodid' in content_lower:
        if 'roundcube' in content_lower:
            return 'Roundcube'
        if 'infomaniak' in content_lower:
            return 'Infomaniak'
        if 'proton' in content_lower:
            return 'Proton'
        if 'thunderbird' in content_lower or 'cardbook' in content_lower:
            return 'Thunderbird'
        if 'apple' in content_lower or 'addressbook' in content_lower:
            return 'Apple'
        if 'google' in content_lower:
            return 'Google'
    # Heuristiques sur le format UID
    if 'uid:proton-' in content_lower:
        return 'Proton'
    # UID Roundcube/SOGo : 32hex-16hex (pas de PRODID)
    import re
    if re.search(r'UID:[0-9A-F]{32}-[0-9A-F]{16}', content):
        return 'Roundcube'
    return 'vCard'


def _import_contact_from_row(row, update_existing=False, source='Import'):
    """
    Importe un contact depuis un dict (TSV ou vCard).

    Détection des doublons :
      1. Par UID (identité exacte, si présent dans le fichier importé)
      2. Par composite email + nom + prénom (même personne probable)
      3. Sinon → nouveau contact créé (même si l'email existe déjà)

    Retourne (contact, action) où action = 'created', 'updated', 'no_email' ou 'skipped'.
    """
    fields = _extract_fields_from_row(row)

    if not fields['email']:
        return None, 'no_email'

    existing = None

    # Priorité 1 : correspondance par UID
    if fields['uid']:
        existing = Contact.query.filter_by(uid=fields['uid']).first()

    # Priorité 2 : correspondance composite email + nom + prénom
    if not existing and fields['nom'] and fields['prenom']:
        existing = Contact.query.filter_by(
            email=fields['email'],
            nom=fields['nom'],
            prenom=fields['prenom']
        ).first()

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
        if fields['adresse_rue']:
            existing.adresse_rue = fields['adresse_rue']
        if fields['adresse_complement']:
            existing.adresse_complement = fields['adresse_complement']
        if fields['adresse_ville']:
            existing.adresse_ville = fields['adresse_ville']
        if fields['adresse_cp']:
            existing.adresse_cp = fields['adresse_cp']
        if fields['adresse_region']:
            existing.adresse_region = fields['adresse_region']
        if fields['adresse_pays']:
            existing.adresse_pays = fields['adresse_pays']
        if fields['notes']:
            existing.notes = fields['notes']

        # Remplacement des listes par celles de l'import
        if fields['listes']:
            existing.listes = _get_or_create_listes(fields['listes'])

        return existing, 'updated'

    # Nouveau contact (même si l'email existe déjà chez un autre contact)
    kwargs = dict(
        nom=fields['nom'],
        prenom=fields['prenom'],
        email=fields['email'],
        telephone=fields['telephone'],
        organisation=fields['organisation'],
        adresse_rue=fields['adresse_rue'],
        adresse_complement=fields['adresse_complement'],
        adresse_ville=fields['adresse_ville'],
        adresse_cp=fields['adresse_cp'],
        adresse_region=fields['adresse_region'],
        adresse_pays=fields['adresse_pays'],
        notes=fields['notes'],
        source=fields.get('source') or source
    )
    # Préserver le UID d'origine (Roundcube, Proton, etc.) s'il est fourni
    if fields['uid']:
        kwargs['uid'] = fields['uid']
    contact = Contact(**kwargs)
    contact.listes = _get_or_create_listes(fields['listes'])

    return contact, 'created'


@app.route('/import', methods=['GET', 'POST'])
@admin_required
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
            source = 'Import'

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

                # Auto-détection de la source depuis le contenu vCard
                source = _detect_vcard_source(content.decode('utf-8', errors='replace'))

            else:
                # === IMPORT TSV/CSV ===
                content = file.read().decode('utf-8')
                first_line = content.split('\n')[0]
                delimiter = '\t' if '\t' in first_line else ','
                reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
                rows = list(reader)
                source = 'TSV' if delimiter == '\t' else 'CSV'

            for row in rows:
                contact, action = _import_contact_from_row(row, update_existing=update_existing, source=source)
                if action == 'created':
                    contact.created_by_id = current_user.id
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
@admin_required
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
    writer.writerow(['UID', 'Nom', 'Prenom', 'Email', 'Telephone', 'Organisation',
                      'Rue', 'Complement', 'Ville', 'CP', 'Region', 'Pays',
                      'Source', 'Notes', 'Listes'])

    for c in contacts:
        writer.writerow([
            c.uid, c.nom, c.prenom, c.email, c.telephone or '',
            c.organisation or '',
            c.adresse_rue or '', c.adresse_complement or '',
            c.adresse_ville or '', c.adresse_cp or '',
            c.adresse_region or '', c.adresse_pays or '',
            c.source or '',
            c.notes or '',
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
    if not liste.contacts:
        return jsonify({'error': 'Liste vide'}), 400

    # Sélectionner le contact par index (borné)
    total = len(liste.contacts)
    contact_index = max(0, min(contact_index, total - 1))
    contact = liste.contacts[contact_index]
    contact_dict = contact.to_dict()

    # Remplacer les variables
    preview_subject = subject
    preview_body = body
    for key, value in contact_dict.items():
        preview_subject = preview_subject.replace(f'{{{key}}}', str(value or ''))
        preview_body = preview_body.replace(f'{{{key}}}', str(value or ''))

    # Ajouter le footer de désabonnement dans la preview
    if include_unsubscribe:
        unsub_url = f"{Config.BASE_URL}/unsubscribe/{contact.uid}"
        if mail_format == 'html':
            preview_body += (
                '<hr><p style="font-size:14px;color:#999;">'
                f'Pour vous désabonner : <a href="{unsub_url}">cliquer ici</a></p>'
            )
        else:
            preview_body += f'\n\n---\nPour vous désabonner : {unsub_url}'

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
    if not liste.contacts:
        flash('Liste vide', 'error')
        return redirect(url_for('mailing'))

    include_unsubscribe = request.form.get('include_unsubscribe') == 'on'

    # Filtrer les contacts désabonnés
    active_contacts = [c for c in liste.contacts if not c.is_unsubscribed]
    excluded = len(liste.contacts) - len(active_contacts)
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
    attachment_paths = []
    uploaded_files = request.files.getlist('attachments')
    if uploaded_files and uploaded_files[0].filename:
        attach_dir = Path(f'data/attachments/{campaign_id}')
        attach_dir.mkdir(parents=True, exist_ok=True)
        for f in uploaded_files:
            if f.filename:
                filename = secure_filename(f.filename)
                if filename:
                    filepath = attach_dir / filename
                    f.save(str(filepath))
                    attachment_paths.append(str(filepath))

    # Ajouter à la file d'attente et sauvegarder le template
    queue = MailQueue()
    queue.set_campaign_template(campaign_id, subject, body, mail_format,
                                sent_by=current_user.username,
                                include_unsubscribe=include_unsubscribe,
                                attachments=attachment_paths or None)
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
            mailer.send_single(contact['email'], subj, body_text, body_html,
                               unsubscribe_url=unsub_url, attachments=attachments)
            queue.mark_sent(item['id'])
            sent += 1
        except Exception as e:
            queue.mark_error(item['id'], str(e))
            errors += 1
        time.sleep(delay)

    # Envoyer une copie à l'expéditeur (trace de la campagne)
    if sent > 0:
        try:
            first_contact = pending[0]['contact']
            subj, body_text, body_html = template.render(first_contact)
            copy_subject = f"[Campagne] {subj}"
            mailer.send_single(Config.SMTP_SENDER_EMAIL, copy_subject, body_text, body_html)
        except Exception:
            pass  # Ne pas bloquer si la copie échoue

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


# === GESTION DES UTILISATEURS (admin only) ===

@app.route('/users')
@admin_required
def users():
    users_list = User.query.order_by(User.username).all()
    return render_template('users.html', users=users_list)


@app.route('/users/new', methods=['GET', 'POST'])
@admin_required
def user_new():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'user')

        if not username or not password:
            flash('Identifiant et mot de passe requis', 'error')
            return render_template('user_form.html', user=None)

        if User.query.filter_by(username=username).first():
            flash(f'L\'identifiant "{username}" existe déjà', 'error')
            return render_template('user_form.html', user=None)

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
            return redirect(url_for('users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    return render_template('user_form.html', user=None)


@app.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@admin_required
def user_edit(id):
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
            return render_template('user_form.html', user=user)

        # Vérifier unicité du username si changé
        if username != user.username:
            if User.query.filter_by(username=username).first():
                flash(f'L\'identifiant "{username}" existe déjà', 'error')
                return render_template('user_form.html', user=user)

        if role not in ('admin', 'user'):
            role = 'user'

        user.username = username
        user.nom = nom
        user.prenom = prenom
        user.email = email or None
        user.role = role

        if password:
            user.password_hash = generate_password_hash(password)

        try:
            db.session.commit()
            flash(f'Utilisateur "{username}" mis à jour', 'success')
            return redirect(url_for('users'))
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {e}', 'error')

    return render_template('user_form.html', user=user)


@app.route('/users/<int:id>/delete', methods=['POST'])
@admin_required
def user_delete(id):
    user = User.query.get_or_404(id)

    if user.id == current_user.id:
        flash('Vous ne pouvez pas supprimer votre propre compte', 'error')
        return redirect(url_for('users'))

    username = user.username
    db.session.delete(user)
    db.session.commit()
    flash(f'Utilisateur "{username}" supprimé', 'success')
    return redirect(url_for('users'))


@app.route('/users/<int:id>/toggle-active', methods=['POST'])
@admin_required
def user_toggle_active(id):
    user = User.query.get_or_404(id)

    if user.id == current_user.id:
        flash('Vous ne pouvez pas désactiver votre propre compte', 'error')
        return redirect(url_for('users'))

    user.is_active = not user.is_active
    db.session.commit()
    status = 'activé' if user.is_active else 'désactivé'
    flash(f'Compte "{user.username}" {status}', 'success')
    return redirect(url_for('users'))


# === PROFIL ===

@app.route('/profile', methods=['GET', 'POST'])
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


# === DESABONNEMENT ===

@app.route('/unsubscribe/<uid>', methods=['GET', 'POST'])
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


@app.route('/contacts/<int:id>/resubscribe', methods=['POST'])
@login_required
def contact_resubscribe(id):
    """Réabonner un contact (admin)"""
    contact = Contact.query.get_or_404(id)
    contact.is_unsubscribed = False
    contact.unsubscribed_at = None
    db.session.commit()
    flash(f'{contact.prenom} {contact.nom} a été réabonné', 'success')
    return redirect(url_for('contact_edit', id=contact.id))


# === MOT DE PASSE OUBLIE ===

@app.route('/forgot-password', methods=['GET', 'POST'])
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
        return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')


# === BOOKSTACK ===

@app.route('/bookstack')
@admin_required
def bookstack():
    roles = BookstackRole.query.order_by(BookstackRole.display_name).all()
    listes = Liste.query.order_by(Liste.nom).all()
    bs_configured = bool(Config.BOOKSTACK_URL and Config.BOOKSTACK_TOKEN_ID and Config.BOOKSTACK_TOKEN_SECRET)
    return render_template('bookstack.html', roles=roles, listes=listes, bs_configured=bs_configured)


@app.route('/bookstack/sync-roles', methods=['POST'])
@admin_required
def bookstack_sync_roles():
    from bookstack import BookstackClient
    from datetime import datetime

    if not Config.BOOKSTACK_URL:
        flash('BookStack non configuré', 'error')
        return redirect(url_for('bookstack'))

    try:
        client = BookstackClient(Config.BOOKSTACK_URL, Config.BOOKSTACK_TOKEN_ID, Config.BOOKSTACK_TOKEN_SECRET)
        data = client.list_roles()
        bs_roles = data.get('data', [])

        now = datetime.utcnow()
        bs_ids = set()

        for r in bs_roles:
            bs_ids.add(r['id'])
            existing = BookstackRole.query.get(r['id'])
            if existing:
                existing.display_name = r['display_name']
                existing.synced_at = now
            else:
                db.session.add(BookstackRole(id=r['id'], display_name=r['display_name'], synced_at=now))

        # Supprimer les rôles qui n'existent plus dans BS
        BookstackRole.query.filter(~BookstackRole.id.in_(bs_ids)).delete(synchronize_session=False)

        db.session.commit()
        flash(f'{len(bs_roles)} rôles synchronisés depuis BookStack', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erreur BookStack : {e}', 'error')

    return redirect(url_for('bookstack'))


@app.route('/bookstack/push', methods=['POST'])
@admin_required
def bookstack_push():
    from bookstack import BookstackClient, push_contacts_to_bookstack

    if not Config.BOOKSTACK_URL:
        flash('BookStack non configuré', 'error')
        return redirect(url_for('bookstack'))

    liste_id = request.form.get('liste_id', type=int)
    role_id = request.form.get('role_id', type=int)

    if not liste_id or not role_id:
        flash('Sélectionnez une liste et un rôle', 'error')
        return redirect(url_for('bookstack'))

    liste = Liste.query.get_or_404(liste_id)
    if not liste.contacts:
        flash('Liste vide', 'error')
        return redirect(url_for('bookstack'))

    try:
        send_invite = request.form.get('send_invite') == 'on'
        client = BookstackClient(Config.BOOKSTACK_URL, Config.BOOKSTACK_TOKEN_ID, Config.BOOKSTACK_TOKEN_SECRET)
        result = push_contacts_to_bookstack(client, liste.contacts, role_id, send_invite=send_invite)

        parts = []
        if result['created']:
            parts.append(f'{result["created"]} créés')
        if result['updated']:
            parts.append(f'{result["updated"]} mis à jour')
        if result['skipped']:
            parts.append(f'{result["skipped"]} inchangés')
        if result['errors']:
            parts.append(f'{len(result["errors"])} erreurs')

        msg = f'Push vers BookStack : {", ".join(parts)}'
        category = 'success' if not result['errors'] else 'warning'
        flash(msg, category)

        for err in result['errors']:
            flash(f'Erreur : {err}', 'error')

    except Exception as e:
        flash(f'Erreur BookStack : {e}', 'error')

    return redirect(url_for('bookstack'))


init_db()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
