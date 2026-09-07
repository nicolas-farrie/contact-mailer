import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.absolute()


def _git_head_short():
    """SHA court de HEAD lu directement dans .git, sans le binaire git.

    Sert de repli en dev : le conteneur monte le code en volumes (hot-reload), donc
    la version figée au build ment dès le commit suivant. Lire HEAD au démarrage
    donne le commit réellement monté. Renvoie '' hors dépôt git (cas de l'image).
    """
    try:
        git_dir = BASE_DIR / '.git'
        head = (git_dir / 'HEAD').read_text().strip()
        if not head.startswith('ref: '):
            return head[:7]  # HEAD détachée : le SHA est écrit tel quel
        ref = head[5:].strip()
        ref_file = git_dir / ref
        if ref_file.exists():
            return ref_file.read_text().strip()[:7]
        # Référence empaquetée (git gc) : la retrouver dans packed-refs
        for line in (git_dir / 'packed-refs').read_text().splitlines():
            if line.endswith(' ' + ref):
                return line.split(' ', 1)[0][:7]
    except OSError:
        pass
    return ''


def _version_file():
    """(version, périmée) lues dans .version — généré par le Makefile ou le hook git.

    Le conteneur n'a pas le binaire git : `git describe` (tag + distance) ne peut pas
    être recalculé au runtime, on le lit donc dans ce fichier. Sa 2e ligne porte le SHA
    de HEAD au moment de la génération ; le comparer à HEAD dit si le fichier a décroché
    du code réellement monté — mieux vaut signaler un tag périmé que l'afficher pour vrai.
    """
    try:
        lines = (BASE_DIR / '.version').read_text().split()
    except OSError:  # absent, ou répertoire créé par un montage Docker sans fichier
        return '', False
    if not lines:
        return '', False
    described, stamped = lines[0], (lines[1] if len(lines) > 1 else '')
    head = _git_head_short()
    return described, bool(head and stamped and head != stamped)


# Version : l'env prime (injecté au build en prod), sinon le fichier, sinon 'dev'.
# 'dev' est le défaut du Dockerfile, donc traité comme « non renseigné ».
_ENV_VERSION = os.environ.get('APP_VERSION', '')
_FILE_VERSION, _FILE_STALE = _version_file()


class Config:
    # Version de l'image, injectée au build (cf. Dockerfile ARG/ENV, Makefile) —
    # affichée dans le header pour identifier la version tournant sur chaque instance.
    APP_VERSION = (_ENV_VERSION if _ENV_VERSION != 'dev' else '') or _FILE_VERSION or 'dev'
    # Vrai quand la version vient d'un .version qui a décroché du code monté.
    APP_VERSION_STALE = _FILE_STALE and APP_VERSION == _FILE_VERSION

    # Identité précise de la build, pour le débogage (affichée sur /a-propos).
    # GIT_COMMIT vient du build en prod ; à défaut on lit HEAD au démarrage, ce qui
    # couvre le dev où le code monté n'est pas celui de l'image.
    GIT_COMMIT = os.environ.get('GIT_COMMIT', '') or _git_head_short()
    BUILD_DATE = os.environ.get('BUILD_DATE', '')
    # Vrai quand le commit n'a pas été figé au build : le code peut avoir bougé depuis.
    GIT_COMMIT_IS_LIVE = not os.environ.get('GIT_COMMIT', '')

    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR}/data/contacts.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Rechargement auto des templates Jinja. DEV uniquement (via env) : évite de
    # redémarrer le conteneur à chaque édition de template. Laisser OFF en prod
    # (templates compilés mis en cache = plus rapide).
    TEMPLATES_AUTO_RELOAD = os.environ.get('TEMPLATES_AUTO_RELOAD', '').lower() in ('1', 'true', 'yes')

    # Admin credentials (à changer en production)
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'changeme')

    # SMTP Configuration
    SMTP_HOST = os.environ.get('SMTP_HOST', '')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_USER = os.environ.get('SMTP_USER', '')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
    SMTP_SENDER_EMAIL = os.environ.get('SMTP_SENDER_EMAIL', '')
    SMTP_SENDER_NAME = os.environ.get('SMTP_SENDER_NAME', '')
    SMTP_USE_TLS = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'

    # Rate limiting (emails par minute) — cadence des envois pour ne pas « bursté »
    # les anti-spam des SMTP mutualisés (LWS…). Défaut prudent ; ajustable en .env.
    MAIL_RATE_PER_MINUTE = int(os.environ.get('MAIL_RATE_PER_MINUTE', 10))
    # Plafonds glissants (fenêtres 1h / 24h) tous envois confondus. 0 = illimité.
    # Au-delà, l'envoi en cours S'ARRÊTE proprement (le reste reste en file, à
    # reprendre plus tard). À CALIBRER sur la limite réelle de l'offre d'hébergement.
    MAIL_MAX_PER_HOUR = int(os.environ.get('MAIL_MAX_PER_HOUR', 100))
    MAIL_MAX_PER_DAY = int(os.environ.get('MAIL_MAX_PER_DAY', 300))

    # URL publique (pour les liens de désabonnement)
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

    # Niveau de log applicatif (DEBUG/INFO/WARNING/ERROR). Défaut INFO.
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()

    # Rétention du journal d'audit (mois) — purge auto au-delà (donnée perso, RGPD).
    AUDIT_RETENTION_MONTHS = int(os.environ.get('AUDIT_RETENTION_MONTHS', 12))

    # Nom et couleur de l'instance (multi-instance, PWA manifest + icône)
    INSTANCE_NAME = os.environ.get('INSTANCE_NAME', '')
    INSTANCE_COLOR = os.environ.get('INSTANCE_COLOR', '#2563eb')
    # Nom d'affichage UI (découplé du nom technique, affiché dans navbar et login)
    DISPLAY_NAME = os.environ.get('DISPLAY_NAME', '')

    # BookStack API
    BOOKSTACK_URL = os.environ.get('BOOKSTACK_URL', '')
    BOOKSTACK_TOKEN_ID = os.environ.get('BOOKSTACK_TOKEN_ID', '')
    BOOKSTACK_TOKEN_SECRET = os.environ.get('BOOKSTACK_TOKEN_SECRET', '')

    # Taille max d'une requête. Le front plafonne le CONTENU à 25 Mo (images
    # embarquées + PJ) ; mais les images en base64 gonflent la requête (~+33 %),
    # d'où 35 Mo ici comme garde-fou serveur (au-delà → 413). Configurable.
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_MB', 35)) * 1024 * 1024

    # Seafile API
    SEAFILE_URL = os.environ.get('SEAFILE_URL', '')
    SEAFILE_TOKEN = os.environ.get('SEAFILE_TOKEN', '')

    # IMAP - boîte bounce (Return-Path des mailings)
    BOUNCE_IMAP_HOST = os.environ.get('BOUNCE_IMAP_HOST', '')
    BOUNCE_IMAP_PORT = int(os.environ.get('BOUNCE_IMAP_PORT', 993))
    BOUNCE_IMAP_USER = os.environ.get('BOUNCE_IMAP_USER', '')
    BOUNCE_IMAP_PASSWORD = os.environ.get('BOUNCE_IMAP_PASSWORD', '')
    BOUNCE_IMAP_FOLDER = os.environ.get('BOUNCE_IMAP_FOLDER', 'INBOX')
    BOUNCE_IMAP_PROCESSED_FOLDER = os.environ.get('BOUNCE_IMAP_PROCESSED_FOLDER', 'Traite')
    # Adresse Return-Path injectée dans les mailings (= BOUNCE_IMAP_USER si non défini)
    BOUNCE_RETURN_PATH = os.environ.get('BOUNCE_RETURN_PATH', '')

    # IMAP - boîte de réception des demandes de diffusion
    IMAP_HOST = os.environ.get('IMAP_HOST', '')
    IMAP_PORT = int(os.environ.get('IMAP_PORT', 993))
    IMAP_USER = os.environ.get('IMAP_USER', '')
    IMAP_PASSWORD = os.environ.get('IMAP_PASSWORD', '')
    IMAP_FOLDER = os.environ.get('IMAP_FOLDER', 'INBOX')
    IMAP_PROCESSED_FOLDER = os.environ.get('IMAP_PROCESSED_FOLDER', 'Traite')
    # Filtre optionnel : seuls les messages dont le sujet contient cette chaîne
    # sont considérés comme des demandes (laisser vide = tous les messages du dossier)
    IMAP_SUBJECT_FILTER = os.environ.get('IMAP_SUBJECT_FILTER', '')
    # Filtre optionnel : seuls les messages adressés à cet alias (en-tête To)
    # sont considérés comme des demandes (laisser vide = tous les messages du dossier)
    IMAP_TO_FILTER = os.environ.get('IMAP_TO_FILTER', '')
