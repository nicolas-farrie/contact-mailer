#!/usr/bin/env python3
"""
Crée ou met à jour le compte administrateur.

Usage:
    python tools/setadmin.py --username admin --password monmdp
    python tools/setadmin.py --password nouveaumdp
    python tools/setadmin.py --username admin --password mdp --role admin --nom Dupont --prenom Jean --email admin@example.com
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
    parser.add_argument('--role', '-r', default='admin', choices=['admin', 'user'], help='Rôle (défaut: admin)')
    parser.add_argument('--nom', default='', help='Nom de famille')
    parser.add_argument('--prenom', default='', help='Prénom')
    parser.add_argument('--email', default='', help='Email')
    args = parser.parse_args()

    with app.app_context():
        user = User.query.filter_by(username=args.username).first()

        if user:
            user.password_hash = generate_password_hash(args.password)
            user.role = args.role
            if args.nom:
                user.nom = args.nom
            if args.prenom:
                user.prenom = args.prenom
            if args.email:
                user.email = args.email
            db.session.commit()
            print(f'Utilisateur "{args.username}" mis à jour (role={args.role})')
        else:
            user = User(
                username=args.username,
                password_hash=generate_password_hash(args.password),
                role=args.role,
                nom=args.nom or None,
                prenom=args.prenom or None,
                email=args.email or None,
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            print(f'Utilisateur "{args.username}" créé (role={args.role})')


if __name__ == '__main__':
    main()
