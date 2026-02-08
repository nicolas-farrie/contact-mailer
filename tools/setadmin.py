#!/usr/bin/env python3
"""
Crée ou met à jour le compte administrateur.

Usage:
    python tools/setadmin.py --username admin --password monmdp
    python tools/setadmin.py --password nouveaumdp
    python tools/setadmin.py --username admin --password mdp --email admin@example.com
"""
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User
from werkzeug.security import generate_password_hash


def main():
    parser = argparse.ArgumentParser(description='Gérer le compte administrateur')
    parser.add_argument('--username', '-u', default='admin', help='Nom d\'utilisateur (défaut: admin)')
    parser.add_argument('--password', '-p', required=True, help='Mot de passe')
    args = parser.parse_args()

    with app.app_context():
        user = User.query.filter_by(username=args.username).first()

        if user:
            user.password_hash = generate_password_hash(args.password)
            db.session.commit()
            print(f'Mot de passe mis à jour pour "{args.username}"')
        else:
            user = User(
                username=args.username,
                password_hash=generate_password_hash(args.password)
            )
            db.session.add(user)
            db.session.commit()
            print(f'Utilisateur "{args.username}" créé')


if __name__ == '__main__':
    main()
