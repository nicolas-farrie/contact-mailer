#!/usr/bin/env python
"""
vcard_converter - Convertisseur bidirectionnel vCard <-> TSV

Supporte les formats vCard 2.1, 3.0 (RFC 2426) et 4.0 (RFC 6350).

Usage:
    vcard_converter.py totsv -i input.vcf -o output.tsv
    vcard_converter.py tovcard -i input.tsv -o output.vcf [-V 3.0|4.0]
"""
import vobject
import glob
import csv
import argparse
import os.path
import sys
import logging
import re

# Séparateur pour les valeurs multiples dans une même cellule
MULTI_VALUE_SEP = ' | '

# Mapping des clés vCard vers noms de colonnes français
VCARD_TO_COL = {
    'version': 'Version',
    'uid': 'UID',
    'prodid': 'Prodid',
    'n': 'Nom, Prénom',
    'fn': 'Nom Complet',
    'email': 'Email',
    'adr': 'Adresse',
    'note': 'Note',
    'bday': 'Date de Naissance',
    'x-gender': 'Genre',
    'x-spouse': 'Compagne/Compagnon',
    'org': 'Organisation',
    'title': 'Titre',
    'url': 'URL',
    'categories': 'Catégories',
    'nickname': 'Surnom',
}

# Types de téléphone reconnus -> colonnes séparées
TEL_TYPES = ['cell', 'home', 'work', 'fax', 'pager', 'voice']
TEL_COLS = {t: f'Tel_{t.capitalize()}' for t in TEL_TYPES}
TEL_COLS['other'] = 'Tel_Autre'

# Types d'email reconnus -> colonnes séparées
EMAIL_TYPES = ['home', 'work']
EMAIL_COLS = {t: f'Email_{t.capitalize()}' for t in EMAIL_TYPES}
EMAIL_COLS['other'] = 'Email_Autre'

# Mapping inverse (colonne -> clé vCard)
COL_TO_VCARD = {v: k for k, v in VCARD_TO_COL.items()}


# =============================================================================
# Fonctions utilitaires
# =============================================================================

def clean_value(value):
    """Nettoie une valeur : supprime retours à la ligne, espaces multiples."""
    if value is None:
        return ''
    value = str(value)
    value = value.replace('\n', ', ').replace('\r', '')
    value = re.sub(r',\s*,', ',', value)
    value = re.sub(r'\s+', ' ', value)
    return value.strip(' ,')


def get_tel_type(tel_obj):
    """Extrait le type d'un numéro de téléphone depuis l'objet vobject."""
    try:
        params = tel_obj.params.get('TYPE', [])
        if isinstance(params, str):
            params = [params]
        params = [p.lower() for p in params]
        for t in TEL_TYPES:
            if t in params:
                return t
    except (AttributeError, KeyError):
        pass
    return 'other'


def get_email_type(email_obj):
    """Extrait le type d'un email depuis l'objet vobject."""
    try:
        params = email_obj.params.get('TYPE', [])
        if isinstance(params, str):
            params = [params]
        params = [p.lower() for p in params]
        for t in EMAIL_TYPES:
            if t in params:
                return t
    except (AttributeError, KeyError):
        pass
    return 'other'


def clean_tel_value(value):
    """Nettoie un numéro de téléphone (supprime préfixe tel:)."""
    value = str(value).strip()
    return re.sub(r'^tel:', '', value, flags=re.IGNORECASE)


# =============================================================================
# vCard -> TSV
# =============================================================================

def extract_vcard_data(vcard, filepath):
    """Extrait les données d'une vCard dans un dictionnaire plat (approche hybride)."""
    data = {}

    # Champs simples
    for vcard_key, col_name in VCARD_TO_COL.items():
        if vcard_key in ('n', 'fn', 'email', 'tel', 'adr', 'categories', 'org'):
            continue  # Traitement spécial
        try:
            val = getattr(vcard, vcard_key, None)
            if val:
                data[col_name] = clean_value(val.value)
        except AttributeError:
            pass

    # Champ N (nom structuré)
    try:
        if hasattr(vcard, 'n') and vcard.n.value:
            vn = vcard.n.value
            data['Nom, Prénom'] = f"{vn.family},{vn.given}".strip(',')
    except AttributeError:
        pass

    # Champ FN (nom complet)
    try:
        if hasattr(vcard, 'fn') and vcard.fn.value:
            data['Nom Complet'] = clean_value(vcard.fn.value)
    except AttributeError:
        pass

    # Téléphones multiples -> colonnes par type
    tel_by_type = {t: [] for t in list(TEL_COLS.keys())}
    try:
        for tel in vcard.tel_list:
            tel_type = get_tel_type(tel)
            tel_value = clean_tel_value(tel.value)
            tel_by_type[tel_type].append(tel_value)
    except AttributeError:
        pass

    for tel_type, col_name in TEL_COLS.items():
        if tel_by_type[tel_type]:
            data[col_name] = MULTI_VALUE_SEP.join(tel_by_type[tel_type])

    # Emails multiples -> colonnes par type
    email_by_type = {t: [] for t in list(EMAIL_COLS.keys())}
    try:
        for email in vcard.email_list:
            email_type = get_email_type(email)
            email_value = clean_value(email.value)
            email_by_type[email_type].append(email_value)
    except AttributeError:
        pass

    for email_type, col_name in EMAIL_COLS.items():
        if email_by_type[email_type]:
            data[col_name] = MULTI_VALUE_SEP.join(email_by_type[email_type])

    # Adresses -> concaténées avec séparateur
    try:
        addresses = []
        for adr in vcard.adr_list:
            adr_str = clean_value(str(adr.value))
            if adr_str:
                addresses.append(adr_str)
        if addresses:
            data['Adresse'] = MULTI_VALUE_SEP.join(addresses)
    except AttributeError:
        pass

    # Catégories -> liste avec séparateur
    try:
        if hasattr(vcard, 'categories') and vcard.categories.value:
            cats = vcard.categories.value
            if isinstance(cats, (list, tuple)):
                data['Catégories'] = MULTI_VALUE_SEP.join(str(c) for c in cats)
            else:
                data['Catégories'] = clean_value(cats)
    except AttributeError:
        pass

    # Organisation -> peut être une liste hiérarchique (Company;Department)
    try:
        if hasattr(vcard, 'org') and vcard.org.value:
            org_val = vcard.org.value
            if isinstance(org_val, (list, tuple)):
                data['Organisation'] = ' - '.join(str(o) for o in org_val if o)
            else:
                data['Organisation'] = clean_value(org_val)
    except AttributeError:
        pass

    return data


def get_vcards(filepath):
    """Génère les vCards depuis un fichier .vcf."""
    with open(filepath, encoding='utf-8') as fp:
        all_text = fp.read()
    for vcard in vobject.readComponents(all_text):
        yield vcard


def vcard_to_tsv(input_paths, output_file, verbose=False):
    """Convertit des fichiers vCard en un fichier TSV."""
    all_data = []
    all_columns = set()

    for filepath in input_paths:
        logging.info(f"Lecture de {filepath}")
        for vcard in get_vcards(filepath):
            data = extract_vcard_data(vcard, filepath)
            all_data.append(data)
            all_columns.update(data.keys())

    if not all_data:
        logging.error("Aucun contact trouvé")
        return False

    # Ordre des colonnes
    priority = [
        'Version', 'UID', 'Nom Complet', 'Nom, Prénom',
        'Tel_Cell', 'Tel_Home', 'Tel_Work', 'Tel_Fax', 'Tel_Autre',
        'Email_Home', 'Email_Work', 'Email_Autre',
        'Adresse', 'Organisation', 'Titre', 'Catégories', 'Note'
    ]
    ordered = [c for c in priority if c in all_columns]
    remaining = sorted(all_columns - set(ordered))
    fieldnames = ordered + remaining

    logging.info(f"Colonnes: {fieldnames}")
    logging.info(f"Contacts: {len(all_data)}")

    with open(output_file, 'w', encoding='utf-8', newline='') as fp:
        writer = csv.DictWriter(fp, fieldnames=fieldnames, delimiter='\t', extrasaction='ignore')
        writer.writeheader()
        for row in all_data:
            writer.writerow(row)

    return True


# =============================================================================
# TSV -> vCard
# =============================================================================

def parse_multi_value(value):
    """Parse une cellule contenant plusieurs valeurs séparées par |."""
    if not value:
        return []
    return [v.strip() for v in value.split('|') if v.strip()]


def create_vcard(row, version='3.0'):
    """Crée un objet vCard depuis une ligne de données TSV."""
    vcard = vobject.vCard()

    # Version
    vcard.add('version').value = version

    # UID
    if row.get('UID'):
        vcard.add('uid').value = row['UID']

    # Nom structuré (N)
    nom_prenom = row.get('Nom, Prénom', '')
    if nom_prenom:
        n = vcard.add('n')
        parts = nom_prenom.split(',', 1)
        family = parts[0].strip() if parts else ''
        given = parts[1].strip() if len(parts) > 1 else ''
        n.value = vobject.vcard.Name(family=family, given=given)

    # Nom complet (FN) - obligatoire
    fn_value = row.get('Nom Complet', '')
    if not fn_value and nom_prenom:
        # Générer depuis N
        parts = nom_prenom.split(',', 1)
        fn_value = ' '.join(reversed([p.strip() for p in parts if p.strip()]))
    if fn_value:
        vcard.add('fn').value = fn_value
    else:
        vcard.add('fn').value = 'Sans nom'

    # Téléphones
    for tel_type, col_name in TEL_COLS.items():
        values = parse_multi_value(row.get(col_name, ''))
        for val in values:
            tel = vcard.add('tel')
            if version == '4.0':
                tel.value = f"tel:{val}" if not val.startswith('tel:') else val
                tel.type_param = tel_type.upper()
            else:
                tel.value = val
                tel.type_param = tel_type.upper()

    # Emails
    for email_type, col_name in EMAIL_COLS.items():
        values = parse_multi_value(row.get(col_name, ''))
        for val in values:
            email = vcard.add('email')
            email.value = val
            email.type_param = email_type.upper()

    # Adresse
    adresses = parse_multi_value(row.get('Adresse', ''))
    for adr_str in adresses:
        adr = vcard.add('adr')
        # Parsing simple : on met tout dans street
        adr.value = vobject.vcard.Address(street=adr_str)

    # Organisation
    if row.get('Organisation'):
        vcard.add('org').value = [row['Organisation']]

    # Titre
    if row.get('Titre'):
        vcard.add('title').value = row['Titre']

    # Catégories
    cats = parse_multi_value(row.get('Catégories', ''))
    if cats:
        vcard.add('categories').value = cats

    # Note
    if row.get('Note'):
        vcard.add('note').value = row['Note']

    # URL
    if row.get('URL'):
        vcard.add('url').value = row['URL']

    # Date de naissance
    if row.get('Date de Naissance'):
        vcard.add('bday').value = row['Date de Naissance']

    # Surnom
    if row.get('Surnom'):
        vcard.add('nickname').value = row['Surnom']

    return vcard


def tsv_to_vcard(input_file, output_file, version='3.0', verbose=False):
    """Convertit un fichier TSV en fichier vCard."""
    vcards = []

    with open(input_file, encoding='utf-8', newline='') as fp:
        reader = csv.DictReader(fp, delimiter='\t')
        for row in reader:
            vcard = create_vcard(row, version)
            vcards.append(vcard)

    if not vcards:
        logging.error("Aucun contact trouvé dans le fichier TSV")
        return False

    logging.info(f"Contacts convertis: {len(vcards)}")

    with open(output_file, 'w', encoding='utf-8') as fp:
        for vcard in vcards:
            fp.write(vcard.serialize())
            fp.write('\n')

    return True


# =============================================================================
# CLI
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Convertisseur bidirectionnel vCard <-> TSV (v2.1, v3.0, v4.0)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s totsv -i contacts.vcf -o contacts.tsv
  %(prog)s totsv -d ./vcards/ -o all_contacts.tsv
  %(prog)s tovcard -i contacts.tsv -o contacts.vcf -V 4.0
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Commande à exécuter')

    # Sous-commande: totsv
    p_totsv = subparsers.add_parser('totsv', help='Convertir vCard(s) vers TSV')
    p_totsv.add_argument('-i', '--input', help='Fichier vCard à convertir')
    p_totsv.add_argument('-d', '--directory', help='Répertoire contenant les fichiers .vcf')
    p_totsv.add_argument('-p', '--pattern', default='*.vcf', help='Pattern de fichiers (défaut: *.vcf)')
    p_totsv.add_argument('-o', '--output', required=True, help='Fichier TSV de sortie')
    p_totsv.add_argument('-v', '--verbose', action='store_true', help='Mode verbeux')

    # Sous-commande: tovcard
    p_tovcard = subparsers.add_parser('tovcard', help='Convertir TSV vers vCard')
    p_tovcard.add_argument('-i', '--input', required=True, help='Fichier TSV à convertir')
    p_tovcard.add_argument('-o', '--output', required=True, help='Fichier vCard de sortie')
    p_tovcard.add_argument('-V', '--version', choices=['3.0', '4.0'], default='3.0',
                          help='Version vCard de sortie (défaut: 3.0)')
    p_tovcard.add_argument('-v', '--verbose', action='store_true', help='Mode verbeux')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Configuration logging
    log_level = logging.INFO if getattr(args, 'verbose', False) else logging.WARNING
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')

    if args.command == 'totsv':
        # Collecter les fichiers d'entrée
        input_paths = []
        if args.input:
            input_paths.append(args.input)
        if args.directory:
            pattern = os.path.join(args.directory, args.pattern)
            input_paths.extend(sorted(glob.glob(pattern)))

        if not input_paths:
            logging.error("Aucun fichier d'entrée spécifié (-i ou -d)")
            sys.exit(2)

        success = vcard_to_tsv(input_paths, args.output, args.verbose)
        sys.exit(0 if success else 1)

    elif args.command == 'tovcard':
        success = tsv_to_vcard(args.input, args.output, args.version, args.verbose)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
