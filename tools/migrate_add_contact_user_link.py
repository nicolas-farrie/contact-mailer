#!/usr/bin/env python3
"""
Migration : ajout de la colonne contact_id à la table user.

Permet de lier un utilisateur applicatif à une fiche contact.

Usage :
    python tools/migrate_add_contact_user_link.py                    # migration réelle
    python tools/migrate_add_contact_user_link.py --dry-run          # simulation sans modification
    python tools/migrate_add_contact_user_link.py --db data/other.db # base personnalisée

Le script :
1. Crée un backup automatique de la base (data/contacts.db.bak.YYYYMMDD_HHMMSS)
2. Vérifie si la colonne contact_id existe déjà (idempotent)
3. Ajoute la colonne contact_id INTEGER REFERENCES contact(id) à la table user
"""
import sqlite3
import shutil
import sys
import os
from datetime import datetime

# Chemin par défaut de la base
DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'contacts.db')


def backup_db(db_path):
    """Crée une copie de sauvegarde horodatée."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.bak.{timestamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def check_already_migrated(conn):
    """Vérifie si la colonne contact_id existe déjà dans la table user."""
    cursor = conn.execute("PRAGMA table_info(user)")
    columns = [row[1] for row in cursor.fetchall()]
    return 'contact_id' in columns


def migrate(db_path, dry_run=False):
    """Exécute la migration."""
    if not os.path.exists(db_path):
        print(f"ERREUR : base introuvable : {db_path}")
        return False

    # Backup
    if not dry_run:
        backup_path = backup_db(db_path)
        print(f"Backup : {backup_path}")
    else:
        print("[DRY-RUN] Pas de backup créé")

    conn = sqlite3.connect(db_path)

    # Vérifier si déjà migré
    if check_already_migrated(conn):
        print("La colonne contact_id existe déjà dans la table user. Migration non nécessaire.")
        conn.close()
        return True

    if dry_run:
        print("[DRY-RUN] Colonne contact_id absente — la migration ajouterait :")
        print("  ALTER TABLE user ADD COLUMN contact_id INTEGER REFERENCES contact(id)")
        print("\n[DRY-RUN] Aucune modification effectuée.")
        conn.close()
        return True

    try:
        conn.execute("ALTER TABLE user ADD COLUMN contact_id INTEGER REFERENCES contact(id)")
        conn.commit()
        print("Migration terminée : colonne contact_id ajoutée à la table user.")

    except Exception as e:
        conn.rollback()
        print(f"ERREUR lors de la migration : {e}")
        conn.close()
        return False

    conn.close()
    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migration : ajout contact_id sur la table user')
    parser.add_argument('--db', default=DEFAULT_DB, help=f'Chemin de la base SQLite (défaut: {DEFAULT_DB})')
    parser.add_argument('--dry-run', action='store_true', help='Simulation sans modification')

    args = parser.parse_args()
    success = migrate(args.db, dry_run=args.dry_run)
    sys.exit(0 if success else 1)