#!/usr/bin/env python3
"""
Réinitialise la base de données.

Usage:
    python tools/resetdb.py              # Réinitialise (crée les tables manquantes)
    python tools/resetdb.py --force      # Supprime et recrée tout (PERTE DE DONNÉES)
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db, init_db


def main():
    parser = argparse.ArgumentParser(description='Réinitialiser la base de données')
    parser.add_argument('--force', action='store_true', help='Supprimer et recréer toutes les tables (PERTE DE DONNÉES)')
    args = parser.parse_args()

    with app.app_context():
        if args.force:
            confirm = input('ATTENTION : Toutes les données seront perdues. Confirmer ? (oui/non) : ')
            if confirm.lower() != 'oui':
                print('Annulé.')
                return
            db.drop_all()
            print('Tables supprimées.')

        db.create_all()
        print('Tables créées.')

        # Créer l'admin par défaut
        from models import User
        from werkzeug.security import generate_password_hash
        from config import Config

        if not User.query.filter_by(username=Config.ADMIN_USERNAME).first():
            admin = User(
                username=Config.ADMIN_USERNAME,
                password_hash=generate_password_hash(Config.ADMIN_PASSWORD)
            )
            db.session.add(admin)
            db.session.commit()
            print(f'Admin "{Config.ADMIN_USERNAME}" créé.')

    print('Base de données prête.')


if __name__ == '__main__':
    main()
