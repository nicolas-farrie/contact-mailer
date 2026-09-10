"""Helpers partagés entre les blueprints : décorateur d'accès admin et
gestion des paramètres applicatifs (table Setting) + fichiers d'upload.

Utilise `current_app` plutôt que d'importer `app` (évite les imports circulaires).
"""
import os
import re
import unicodedata
from functools import wraps

from flask import current_app, url_for, flash, redirect
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import db, Setting, utcnow


def slugify_key(label):
    """Dérive une clé machine stable (fieldName) depuis un libellé.
    Partagé par la gestion des champs perso (Paramètres) et la création à l'import."""
    s = unicodedata.normalize('NFKD', (label or '').strip().lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-z0-9]+', '_', s).strip('_')
    if s and s[0].isdigit():
        s = 'f_' + s
    return s


def backup_database(dest_path):
    """Copie COHÉRENTE de la base SQLite vers `dest_path` via l'API backup de sqlite3
    — sûre même en mode WAL (un `cp` brut raterait les données encore dans le -wal).
    Crée le dossier de destination au besoin. Renvoie le chemin ; peut lever."""
    import sqlite3
    from models import db
    src = db.engine.url.database
    if not src:
        raise RuntimeError('Chemin de la base SQLite introuvable.')
    os.makedirs(os.path.dirname(dest_path) or '.', exist_ok=True)
    src_conn = sqlite3.connect(src)
    dst_conn = sqlite3.connect(dest_path)
    try:
        with dst_conn:
            src_conn.backup(dst_conn)
    finally:
        src_conn.close()
        dst_conn.close()
    return dest_path


def nom_sort_key(nom):
    """Clé de tri alphabétique insensible à la casse ET aux accents. SQLite trie en
    BINARY (majuscules avant minuscules, accents après z) → ordre illisible ; ce
    normaliseur donne l'ordre attendu par un lecteur francophone."""
    s = unicodedata.normalize('NFKD', (nom or '').strip().lower())
    return ' '.join(''.join(c for c in s if not unicodedata.combining(c)).split())


def dedup_key(s):
    """Clé de rapprochement d'un nom : casse, accents ET séparateurs ignorés.

    « Marie-Noëlle », « Marie Noelle » et « marienoelle » donnent la même clé. Les gens
    saisissent un tiret ici, un espace là, une apostrophe ailleurs — l'écart n'a aucune
    valeur informative, et le laisser passer crée des doublons sur des personnes
    manifestement identiques.

    Distincte de nom_sort_key (qui, elle, sert au TRI et à la comparaison de valeurs) :
    supprimer les espaces y placerait « Le Roux » à la lettre « leroux » et ferait passer
    pour identiques des adresses comme « 12 rue X » et « 12rue X ».
    """
    s = unicodedata.normalize('NFKD', (s or '').strip().lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return ''.join(c for c in s if c.isalnum())


# --- Téléphone : comparaison insensible aux séparateurs ---------------------------
# On stocke le numéro tel que saisi (« 06 22 36 39 40 ») ; pour la recherche, on
# compare les CHIFFRES seuls de part et d'autre → « 0622363940 » retrouve le contact.
_PHONE_SEPARATORS = (' ', '.', '-', '(', ')', ' ', '/')


def phone_digits(s):
    """Chiffres seuls d'une chaîne (côté Python), quel que soit le formatage."""
    return re.sub(r'\D', '', s or '')


def phone_digits_sql(col):
    """Expression SQL : `col` dépouillé de ses séparateurs courants (espace, point,
    tiret, parenthèses, /…), pour matcher un numéro indépendamment de son format.
    Ne retire QUE les séparateurs (pas un éventuel « + » de préfixe international)."""
    expr = col
    for sep in _PHONE_SEPARATORS:
        expr = db.func.replace(expr, sep, '')
    return expr


def listes_sorted(is_archived=False):
    """Listes triées lisiblement (cf. nom_sort_key). `is_archived` : False = actives
    (défaut), True = archivées, None = toutes. Source unique du tri des listes dans
    toute l'app (rail mailing, filtres Contacts, formulaires, intégrations…)."""
    from models import Liste
    q = Liste.query
    if is_archived is not None:
        q = q.filter_by(is_archived=is_archived)
    return sorted(q.all(), key=lambda l: nom_sort_key(l.nom))


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


def list_source_label(liste):
    """Nom affichable de la source qui alimente cette liste, ou '' si elle est libre.

    Passe par le registre des connecteurs : le nom du service ne doit apparaître ni dans
    un template, ni dans un message d'erreur écrit en dur.
    """
    src = getattr(liste, 'source', None)
    if src is None:
        return ''
    from connectors import get_connector
    connector = get_connector(src.provider)
    return connector.label if connector else src.provider


def list_edit_blocked_reason(liste):
    """Message si l'appartenance à cette liste ne se modifie pas à la main, sinon None.

    Une liste alimentée est un reflet de sa source : l'y ajouter ou en retirer quelqu'un
    serait défait à la synchronisation suivante, sans un mot. Mieux vaut refuser en
    expliquant que laisser faire un geste qui sera annulé.

    Un seul point de vérité, appelé partout où une appartenance change (fiche contact,
    actions en masse), pour qu'aucun chemin n'échappe à la règle.
    """
    if liste is None or getattr(liste, 'source', None) is None:
        return None
    return (f'« {liste.nom} » est alimentée par {list_source_label(liste)} : '
            f'ses membres suivent la source et ne se modifient pas ici.')


def since_label(dt):
    """« il y a 12 min », « il y a 3 h », « il y a 2 j » — ou '' si jamais.

    Une date brute (« 2026-09-10 08:12 ») oblige à calculer de tête pour savoir si une
    donnée est fraîche. Devant un envoi de mails, c'est cette fraîcheur qui compte, pas
    l'horodatage.
    """
    if not dt:
        return ''
    delta = utcnow() - dt
    minutes = int(delta.total_seconds() // 60)
    if minutes < 1:
        return "à l'instant"
    if minutes < 60:
        return f'il y a {minutes} min'
    if minutes < 60 * 24:
        return f'il y a {minutes // 60} h'
    return f'il y a {minutes // (60 * 24)} j'
