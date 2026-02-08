#!/usr/bin/env python3
"""
Teste la connexion SMTP et envoie un email de test.

Usage:
    python tools/testsmtp.py                          # Teste la connexion uniquement
    python tools/testsmtp.py --to test@example.com    # Envoie un email de test
"""
import argparse
import smtplib
import ssl
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config


def main():
    parser = argparse.ArgumentParser(description='Tester la connexion SMTP')
    parser.add_argument('--to', help='Adresse email pour envoyer un test')
    args = parser.parse_args()

    if not Config.SMTP_HOST:
        print('SMTP non configuré dans .env')
        sys.exit(1)

    print(f'Connexion à {Config.SMTP_HOST}:{Config.SMTP_PORT}...')
    print(f'Utilisateur : {Config.SMTP_USER}')
    print(f'TLS : {Config.SMTP_USE_TLS}')

    try:
        context = ssl.create_default_context()
        if Config.SMTP_USE_TLS:
            server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT)
            server.starttls(context=context)
        else:
            server = smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, context=context)

        server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
        print('Connexion SMTP OK')

        if args.to:
            from email.mime.text import MIMEText
            from email.utils import formataddr, formatdate, make_msgid

            msg = MIMEText('Test de connexion SMTP depuis Contact Mailer.', 'plain', 'utf-8')
            msg['Subject'] = 'Test Contact Mailer'
            msg['From'] = formataddr((Config.SMTP_SENDER_NAME, Config.SMTP_SENDER_EMAIL))
            msg['To'] = args.to
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid(domain=Config.SMTP_SENDER_EMAIL.split('@')[1])
            msg['Content-Language'] = 'fr'

            server.sendmail(Config.SMTP_SENDER_EMAIL, args.to, msg.as_string())
            print(f'Email de test envoyé à {args.to}')

        server.quit()

    except Exception as e:
        print(f'Erreur : {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
