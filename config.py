import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.absolute()


class Config:
    # Version de l'image, injectée au build (cf. Dockerfile ARG/ENV, Makefile) —
    # affichée dans le header pour identifier la version tournant sur chaque instance.
    APP_VERSION = os.environ.get('APP_VERSION', 'dev')

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

    # Rate limiting (emails par minute)
    MAIL_RATE_PER_MINUTE = int(os.environ.get('MAIL_RATE_PER_MINUTE', 20))

    # URL publique (pour les liens de désabonnement)
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')

    # Nom et couleur de l'instance (multi-instance, PWA manifest + icône)
    INSTANCE_NAME = os.environ.get('INSTANCE_NAME', '')
    INSTANCE_COLOR = os.environ.get('INSTANCE_COLOR', '#2563eb')
    # Nom d'affichage UI (découplé du nom technique, affiché dans navbar et login)
    DISPLAY_NAME = os.environ.get('DISPLAY_NAME', '')

    # BookStack API
    BOOKSTACK_URL = os.environ.get('BOOKSTACK_URL', '')
    BOOKSTACK_TOKEN_ID = os.environ.get('BOOKSTACK_TOKEN_ID', '')
    BOOKSTACK_TOKEN_SECRET = os.environ.get('BOOKSTACK_TOKEN_SECRET', '')

    # Taille max d'une requête (formulaire + pièces jointes). 27 Mo = ~25 Mo de PJ
    # (limite Gmail) + marge. Le front (MAX_ATTACH_MB) bloque avant avec un message clair ;
    # ceci est le garde-fou serveur (au-delà → 413).
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_MB', 27)) * 1024 * 1024

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
