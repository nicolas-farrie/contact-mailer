"""Blueprint imports : import TSV/CSV/vCard et export TSV/vCard des contacts.

Endpoints : imports.index (page + traitement import), imports.export_vcard,
imports.export_contacts.
"""
import csv
import io
import os
import uuid
import unicodedata

from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, Response)
from flask_login import login_required, current_user

from models import db, Contact, Liste
from vcard_converter import extract_vcard_data, get_vcards, MULTI_VALUE_SEP
from helpers import admin_required
import fields as fields_registry

bp = Blueprint('imports', __name__)

# Dossier temporaire des fichiers en cours d'import (mappage en 2 temps)
_IMPORT_DIR = 'data/imports'

# Alias de noms de colonnes → clé de champ (auto-suggestion du mapping)
_MAPPING_ALIASES = {
    'courriel': 'email', 'mail': 'email', 'e mail': 'email', 'adresse mail': 'email', 'adresse email': 'email',
    'first name': 'prenom', 'firstname': 'prenom', 'given name': 'prenom',
    'nom de famille': 'nom', 'last name': 'nom', 'lastname': 'nom', 'surname': 'nom',
    'tel': 'telephone', 'phone': 'telephone', 'portable': 'telephone', 'mobile': 'telephone',
    'gsm': 'telephone', 'tel portable': 'telephone', 'numero': 'telephone',
    'commune': 'adresse_ville', 'city': 'adresse_ville',
    'code postal': 'adresse_cp', 'cp': 'adresse_cp', 'zip': 'adresse_cp', 'zip code': 'adresse_cp',
    'adresse': 'adresse_rue', 'rue': 'adresse_rue', 'street': 'adresse_rue', 'voie': 'adresse_rue',
    'complement': 'adresse_complement', 'complement adresse': 'adresse_complement',
    'departement': 'adresse_region', 'region': 'adresse_region',
    'pays': 'adresse_pays', 'country': 'adresse_pays',
    'organization': 'organisation', 'societe': 'organisation', 'entreprise': 'organisation', 'company': 'organisation',
    'note': 'notes', 'remarque': 'notes', 'remarques': 'notes', 'commentaire': 'notes',
    'liste': 'listes', 'categorie': 'listes', 'categories': 'listes', 'groupe': 'listes', 'groupes': 'listes',
}


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


# === Import v2 : mapping registre-driven (Excel/CSV) ===

def _norm(s):
    """Normalise pour matcher : minuscule, sans accents, alphanum, espaces compactés."""
    s = unicodedata.normalize('NFKD', str(s or '')).encode('ascii', 'ignore').decode()
    s = ''.join(c if c.isalnum() else ' ' for c in s.lower())
    return ' '.join(s.split())


def _import_targets():
    """Champs mappables : registre (cœur + perso, éditables) + synthétiques listes/uid."""
    targets = []
    for f in fields_registry.contact_fields(include_custom=True):
        if f.editable:   # 'source' est editable=False → jamais proposé à l'import
            targets.append({'key': f.key, 'label': f.label, 'group': f.group,
                            'custom': (f.source == 'custom')})
    targets.append({'key': 'listes', 'label': 'Listes (séparées par ;)', 'group': 'listes', 'custom': False})
    targets.append({'key': 'uid', 'label': 'UID (dédoublonnage)', 'group': 'systeme', 'custom': False})
    return targets


def _suggest_mapping(headers, targets):
    """Devine {header: clé} par nom (clé/label du registre, puis alias)."""
    by_norm = {}
    for t in targets:
        by_norm.setdefault(_norm(t['label']), t['key'])
        by_norm.setdefault(_norm(t['key']), t['key'])
    out = {}
    for h in headers:
        n = _norm(h)
        out[h] = by_norm.get(n) or _MAPPING_ALIASES.get(n) or ''
    return out


def _read_tabular(path, filename):
    """(headers, rows) depuis .xlsx / .csv / .tsv. rows = list de {header: str}."""
    fn = (filename or '').lower()
    if fn.endswith('.xlsx') or fn.endswith('.xlsm'):
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        ws = wb.active
        it = ws.iter_rows(values_only=True)
        try:
            head = next(it)
        except StopIteration:
            wb.close(); return [], []
        headers = [str(h).strip() if h is not None else f'colonne {i+1}' for i, h in enumerate(head)]
        rows = []
        for r in it:
            d = {h: ('' if (i >= len(r) or r[i] is None) else str(r[i]).strip())
                 for i, h in enumerate(headers)}
            if any(d.values()):
                rows.append(d)
        wb.close()
        return headers, rows
    # CSV / TSV : utf-8 (BOM géré) sinon cp1252 (encodage réel des exports Excel FR).
    # cp1252 mappe les 256 octets → jamais d'échec, et rend correctement é/è/à/ç…
    # (on évite la détection statistique, peu fiable sur de petits fichiers).
    with open(path, 'rb') as fp:
        raw = fp.read()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('cp1252', errors='replace')
    first = text.split('\n', 1)[0]
    delim = '\t' if '\t' in first else (';' if first.count(';') > first.count(',') else ',')
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    headers = [(h or '').strip() for h in (reader.fieldnames or [])]
    rows = []
    for r in reader:
        d = {(k or '').strip(): ('' if v is None else str(v).strip()) for k, v in r.items()}
        if any(d.values()):
            rows.append(d)
    return headers, rows


def _apply_mapping(row, mapping):
    """{clé_champ: valeur} depuis {header: valeur} + {header: clé}. 1re valeur non vide gagne."""
    mapped = {}
    for header, key in mapping.items():
        if not key:
            continue
        val = (row.get(header) or '').strip()
        if val and not mapped.get(key):
            mapped[key] = val
    return mapped


def _key_sets():
    """(clés colonnes, clés perso) éditables du registre."""
    col_keys, custom_keys = set(), set()
    for f in fields_registry.contact_fields(include_custom=True):
        if not f.editable:
            continue
        (custom_keys if f.source == 'custom' else col_keys).add(f.key)
    return col_keys, custom_keys


def _import_mapped(mapped, col_keys, custom_keys, update_existing, source, extra_listes):
    """Importe une row MAPPÉE (keyée par clé de champ). Sans email = ACCEPTÉ.
    Dédup : UID puis composite email+nom+prénom (si email). Retourne (contact, action)."""
    email = (mapped.get('email') or '').strip()
    nom = (mapped.get('nom') or '').strip()
    prenom = (mapped.get('prenom') or '').strip()
    uid = (mapped.get('uid') or '').strip()

    existing = None
    if uid:
        existing = Contact.query.filter_by(uid=uid, is_deleted=False).first()
    if not existing and email and nom and prenom:
        existing = Contact.query.filter_by(email=email, nom=nom, prenom=prenom, is_deleted=False).first()

    if existing and not update_existing:
        return existing, 'skipped'

    listes_names = sorted(set(_parse_liste_names(mapped.get('listes', '')) + list(extra_listes)))

    def _write(contact):
        for key, val in mapped.items():
            if not val or key in ('listes', 'uid'):
                continue
            if key in col_keys:
                setattr(contact, key, val)
            elif key in custom_keys:
                cf = dict(contact.custom_fields or {})
                cf[key] = val
                contact.custom_fields = cf
        if uid and not contact.uid:
            contact.uid = uid
        if listes_names:
            objs = _get_or_create_listes(listes_names)
            if update_existing and existing is contact:
                contact.listes = objs
            else:
                for l in objs:
                    if l not in contact.listes:
                        contact.listes.append(l)

    if existing and update_existing:
        _write(existing)
        return existing, 'updated'

    # Nouveau : colonnes NOT NULL initialisées à '' (contact « à compléter » autorisé)
    contact = Contact(nom='', prenom='', email='', source=(mapped.get('source') or source))
    db.session.add(contact)   # en session AVANT d'attacher les listes (sinon l'assoc n'est pas prise)
    _write(contact)
    return contact, 'created'


def _dry_run(rows, mapping, col_keys, custom_keys, update_existing, extra_listes):
    """Compte created/updated/skipped SANS écrire (rollback à la fin)."""
    counts = {'created': 0, 'updated': 0, 'skipped': 0}
    sample = []
    for i, row in enumerate(rows):
        mapped = _apply_mapping(row, mapping)
        _c, action = _import_mapped(mapped, col_keys, custom_keys, update_existing, 'preview', extra_listes)
        counts[action] = counts.get(action, 0) + 1
        no_email = not (mapped.get('email') or '').strip()
        if no_email and action != 'skipped':
            counts['no_email'] = counts.get('no_email', 0) + 1
        if i < 6:
            sample.append({'mapped': mapped, 'action': action, 'no_email': no_email})
    db.session.rollback()   # défausse toute mutation — rien n'est persisté
    return counts, sample


def _run_import(rows, mapping, col_keys, custom_keys, update_existing, extra_listes, user_id):
    counts = {'created': 0, 'updated': 0, 'skipped': 0, 'no_email': 0}
    for row in rows:
        mapped = _apply_mapping(row, mapping)
        contact, action = _import_mapped(mapped, col_keys, custom_keys, update_existing, 'Import', extra_listes)
        if action == 'created':
            contact.created_by_id = user_id
            db.session.add(contact)
        counts[action] += 1
        if not (mapped.get('email') or '').strip() and action != 'skipped':
            counts['no_email'] += 1
    db.session.commit()
    return counts


def _mapping_from_form(form):
    """Reconstruit {header: clé} depuis les paires cachées hdr/map (ordre préservé)."""
    return dict(zip(form.getlist('hdr'), form.getlist('map')))


def _extra_listes_from(list_id):
    if list_id:
        l = Liste.query.get(int(list_id))
        return [l.nom] if l else []
    return []


# === Routes ===

def _import_vcard_direct(file):
    """Import direct d'un fichier vCard (schéma standard → pas de mapping)."""
    import tempfile
    update_existing = request.form.get('update_existing') == 'on'
    content = file.read()
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.vcf', mode='wb')
    tmp.write(content)
    tmp.close()
    created = updated = skipped = no_email = 0
    try:
        source = _detect_vcard_source(content.decode('utf-8', errors='replace'))
        for vcard in get_vcards(tmp.name):
            row = extract_vcard_data(vcard, tmp.name)
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
        flash('Import vCard : ' + (', '.join(parts) or 'aucun contact'), 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur import vCard : {e}', 'error')
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return redirect(url_for('contacts.index'))


@bp.route('/import', methods=['GET', 'POST'])
@admin_required
def index():
    listes = Liste.query.order_by(Liste.nom).all()
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            flash('Aucun fichier sélectionné', 'error')
            return redirect(url_for('imports.index'))
        fn = file.filename.lower()
        if fn.endswith('.vcf') or fn.endswith('.vcard'):
            return _import_vcard_direct(file)

        # Tabulaire (.xlsx / .csv / .tsv) → sauver en temp + écran de mapping
        os.makedirs(_IMPORT_DIR, exist_ok=True)
        ext = '.xlsx' if fn.endswith(('.xlsx', '.xlsm')) else ('.tsv' if fn.endswith('.tsv') else '.csv')
        token = uuid.uuid4().hex
        path = os.path.join(_IMPORT_DIR, token + ext)
        file.save(path)
        try:
            headers, rows = _read_tabular(path, file.filename)
        except Exception as e:
            try:
                os.remove(path)
            except OSError:
                pass
            flash(f'Lecture du fichier impossible : {e}', 'error')
            return redirect(url_for('imports.index'))
        if not headers:
            try:
                os.remove(path)
            except OSError:
                pass
            flash("Fichier vide ou sans ligne d'en-tête.", 'error')
            return redirect(url_for('imports.index'))
        targets = _import_targets()
        return render_template('import_mapping.html',
                               token=token, ext=ext, filename=file.filename,
                               headers=headers, sample_rows=rows[:5], nrows=len(rows),
                               targets=targets, mapping=_suggest_mapping(headers, targets),
                               listes=listes, list_id=request.form.get('list_id', ''),
                               update_existing=request.form.get('update_existing') == 'on',
                               previewed=False, counts=None, preview=None,
                               field_map=fields_registry.field_map())

    return render_template('import.html', listes=listes)


@bp.route('/import/mapping', methods=['POST'])
@admin_required
def import_mapping():
    token = request.form.get('token', '')
    ext = request.form.get('ext', '')
    path = os.path.join(_IMPORT_DIR, token + ext)
    if not token or not os.path.exists(path):
        flash("Session d'import expirée — recommencez.", 'error')
        return redirect(url_for('imports.index'))

    filename = request.form.get('filename', 'x' + ext)
    mapping = _mapping_from_form(request.form)
    list_id = request.form.get('list_id', '')
    update_existing = request.form.get('update_existing') == 'on'
    action = request.form.get('action', 'preview')

    try:
        headers, rows = _read_tabular(path, filename)
    except Exception as e:
        flash(f'Lecture impossible : {e}', 'error')
        return redirect(url_for('imports.index'))

    col_keys, custom_keys = _key_sets()
    extra = _extra_listes_from(list_id)

    if action == 'run':
        try:
            counts = _run_import(rows, mapping, col_keys, custom_keys, update_existing, extra, current_user.id)
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur import : {e}', 'error')
            return redirect(url_for('imports.index'))
        try:
            os.remove(path)
        except OSError:
            pass
        msg = (f"Import terminé : {counts['created']} créés, {counts['updated']} mis à jour, "
               f"{counts['skipped']} inchangés")
        if counts.get('no_email'):
            msg += f" — dont {counts['no_email']} sans email (à compléter)"
        flash(msg + '.', 'success')
        return redirect(url_for('contacts.index'))

    # preview (dry-run, rien écrit)
    counts, sample = _dry_run(rows, mapping, col_keys, custom_keys, update_existing, extra)
    return render_template('import_mapping.html',
                           token=token, ext=ext, filename=filename,
                           headers=headers, sample_rows=rows[:5], nrows=len(rows),
                           targets=_import_targets(), mapping=mapping,
                           listes=Liste.query.order_by(Liste.nom).all(), list_id=list_id,
                           update_existing=update_existing,
                           previewed=True, counts=counts, preview=sample,
                           field_map=fields_registry.field_map())


@bp.route('/import/template')
@admin_required
def import_template():
    """Modèle CSV généré depuis le registre : en-têtes attendus + une ligne d'exemple."""
    targets = _import_targets()
    example_vals = {'email': 'jean.dupont@exemple.fr', 'nom': 'Dupont', 'prenom': 'Jean',
                    'civilite': 'Monsieur', 'telephone': '06 12 34 56 78',
                    'adresse_ville': 'Lodève', 'adresse_cp': '34700',
                    'listes': 'Sénatoriales 2026'}
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([t['label'] for t in targets])
    w.writerow([example_vals.get(t['key'], '') for t in targets])
    return Response(out.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment; filename=modele_import_contacts.csv'})


@bp.route('/export/vcard')
@admin_required
def export_vcard():
    from vcard_converter import create_vcard
    liste_id = request.args.get('liste', type=int)
    ids = request.args.get('ids', '').strip()
    version = request.args.get('version', '3.0')
    if version not in ('3.0', '4.0'):
        version = '3.0'

    if ids:
        id_list = [int(x) for x in ids.split(',') if x.strip().isdigit()]
        contacts = (Contact.query.filter(Contact.id.in_(id_list), Contact.is_deleted == False)
                    .order_by(Contact.nom, Contact.prenom).all())
        filename = 'contacts_selection.vcf'
    elif liste_id:
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
    ids = request.args.get('ids', '').strip()

    if ids:
        id_list = [int(x) for x in ids.split(',') if x.strip().isdigit()]
        contacts = (Contact.query.filter(Contact.id.in_(id_list), Contact.is_deleted == False)
                    .order_by(Contact.nom, Contact.prenom).all())
        filename = 'contacts_selection.tsv'
    elif liste_id:
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
