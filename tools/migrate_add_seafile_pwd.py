#!/usr/bin/env python3
"""
Migration : ajout du champ seafile_temp_pwd aux contacts.

Usage :
    python tools/migrate_add_seafile_pwd.py                    # migration réelle
    python tools/migrate_add_seafile_pwd.py --dry-run          # simulation sans modification
    python tools/migrate_add_seafile_pwd.py --db data/other.db # base personnalisée
"""
import sqlite3
import shutil
import sys
import os
from datetime import datetime

DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'contacts.db')


def backup_db(db_path):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.bak.{timestamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def get_existing_columns(conn):
    cursor = conn.execute("PRAGMA table_info(contact)")
    return [row[1] for row in cursor.fetchall()]


def migrate(db_path, dry_run=False):
    if not os.path.exists(db_path):
        print(f"ERREUR : base introuvable : {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    columns = get_existing_columns(conn)

    if 'seafile_temp_pwd' in columns:
        print("La colonne seafile_temp_pwd existe déjà. Migration non nécessaire.")
        conn.close()
        return True

    print("Colonne à ajouter : seafile_temp_pwd VARCHAR(100)")

    if dry_run:
        print("\n[DRY-RUN] Aucune modification effectuée.")
        conn.close()
        return True

    backup_path = backup_db(db_path)
    print(f"Backup : {backup_path}")

    try:
        conn.execute("ALTER TABLE contact ADD COLUMN seafile_temp_pwd VARCHAR(100)")
        conn.commit()
        print("  + seafile_temp_pwd ajoutée")
        print("Migration terminée avec succès.")
    except Exception as e:
        conn.rollback()
        print(f"ERREUR lors de la migration : {e}")
        conn.close()
        return False

    conn.close()
    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migration : ajout champ seafile_temp_pwd')
    parser.add_argument('--db', default=DEFAULT_DB, help=f'Chemin de la base SQLite (défaut: {DEFAULT_DB})')
    parser.add_argument('--dry-run', action='store_true', help='Simulation sans modification')

    args = parser.parse_args()
    success = migrate(args.db, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
