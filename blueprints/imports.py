"""Blueprint imports : import TSV/CSV/vCard et export TSV/vCard des contacts.

Endpoints : imports.index (page + traitement import), imports.export_vcard,
imports.export_contacts.
"""
import csv
import io

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, Response)
from flask_login import login_required, current_user

from models import db, Contact, Liste
from vcard_converter import extract_vcard_data, get_vcards, MULTI_VALUE_SEP
from helpers import admin_required

bp = Blueprint('imports', __name__)


# === Helpers d'import ===

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
        'genre': row.get('Genre', row.get('genre', '')).strip(),
        'titre': row.get('Titre', row.get('titre', '')).strip(),
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
        existing = Contact.query.filter_by(uid=fields['uid'], is_deleted=False).first()

    # Priorité 2 : correspondance composite email + nom + prénom
    if not existing and fields['nom'] and fields['prenom']:
        existing = Contact.query.filter_by(
            email=fields['email'],
            nom=fields['nom'],
            prenom=fields['prenom'],
            is_deleted=False
        ).first()

    if existing and not update_existing:
        return None, 'skipped'

    if existing and update_existing:
        # Mettre à jour les champs non vides
        if fields['nom']:
            existing.nom = fields['nom']
        if fields['prenom']:
            existing.prenom = fields['prenom']
        if fields['genre']:
            existing.genre = fields['genre']
        if fields['titre']:
            existing.titre = fields['titre']
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
        genre=fields['genre'],
        titre=fields['titre'],
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


# === Routes ===

@bp.route('/import', methods=['GET', 'POST'])
@admin_required
def index():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            flash('Aucun fichier sélectionné', 'error')
            return redirect(url_for('imports.index'))

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

        return redirect(url_for('contacts.index'))

    return render_template('import.html')


@bp.route('/export/vcard')
@admin_required
def export_vcard():
    from vcard_converter import create_vcard
    liste_id = request.args.get('liste', type=int)
    version = request.args.get('version', '3.0')
    if version not in ('3.0', '4.0'):
        version = '3.0'

    if liste_id:
        liste = Liste.query.get_or_404(liste_id)
        contacts = liste.active_contacts
        filename = f'contacts_{liste.nom}.vcf'
    else:
        contacts = Contact.query.filter(Contact.is_deleted == False).order_by(Contact.nom, Contact.prenom).all()
        filename = 'contacts_all.vcf'

    lines = []
    for c in contacts:
        adr_parts = [c.adresse_rue, c.adresse_complement, c.adresse_ville,
                     c.adresse_cp, c.adresse_region, c.adresse_pays]
        adresse = ', '.join(p for p in adr_parts if p)
        row = {
            'UID': c.uid or '',
            'Nom, Prénom': f"{c.nom},{c.prenom}",
            'Nom Complet': f"{c.prenom} {c.nom}".strip(),
            'Email_Autre': c.email,
            'Tel_Cell': c.telephone or '',
            'Organisation': c.organisation or '',
            'Note': c.notes or '',
            'Adresse': adresse,
            'Catégories': ' | '.join(l.nom for l in c.listes),
        }
        vcard = create_vcard(row, version)
        lines.append(vcard.serialize())

    return Response(
        '\n'.join(lines),
        mimetype='text/vcard',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


@bp.route('/export')
@admin_required
def export_contacts():
    liste_id = request.args.get('liste', type=int)

    if liste_id:
        liste = Liste.query.get_or_404(liste_id)
        contacts = liste.active_contacts
        filename = f'contacts_{liste.nom}.tsv'
    else:
        contacts = Contact.query.filter(Contact.is_deleted == False).order_by(Contact.nom, Contact.prenom).all()
        filename = 'contacts_all.tsv'

    output = io.StringIO()
    writer = csv.writer(output, delimiter='\t')
    writer.writerow(['UID', 'Nom', 'Prenom', 'Genre', 'Titre', 'Email', 'Telephone', 'Organisation',
                      'Rue', 'Complement', 'Ville', 'CP', 'Region', 'Pays',
                      'Source', 'Notes', 'Listes'])

    for c in contacts:
        writer.writerow([
            c.uid, c.nom, c.prenom, c.genre or '', c.titre or '',
            c.email, c.telephone or '',
            c.organisation or '',
            c.adresse_rue or '', c.adresse_complement or '',
            c.adresse_ville or '', c.adresse_cp or '',
            c.adresse_region or '', c.adresse_pays or '',
            c.source or '',
            c.notes or '',
            ','.join([l.nom for l in c.listes])
        ])

    return Response(
        output.getvalue(),
        mimetype='text/tab-separated-values',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )
