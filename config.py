import os
from pathlib import Path

BASE_DIR = Path(__file__).parent.absolute()


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f'sqlite:///{BASE_DIR}/data/contacts.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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

    # Nom de l'instance (multi-instance)
    INSTANCE_NAME = os.environ.get('INSTANCE_NAME', '')

    # BookStack API
    BOOKSTACK_URL = os.environ.get('BOOKSTACK_URL', '')
    BOOKSTACK_TOKEN_ID = os.environ.get('BOOKSTACK_TOKEN_ID', '')
    BOOKSTACK_TOKEN_SECRET = os.environ.get('BOOKSTACK_TOKEN_SECRET', '')
