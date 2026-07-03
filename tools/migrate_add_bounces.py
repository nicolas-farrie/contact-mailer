#!/usr/bin/env python3
"""
Migration : ajout des champs bounce aux contacts.

Usage :
    python tools/migrate_add_bounces.py
    python tools/migrate_add_bounces.py --dry-run
    python tools/migrate_add_bounces.py --db data/other.db
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

    to_add = []
    if 'has_bounced' not in columns:
        to_add.append(('has_bounced', 'BOOLEAN NOT NULL DEFAULT 0'))
    if 'bounced_at' not in columns:
        to_add.append(('bounced_at', 'DATETIME'))

    if not to_add:
        print("Les colonnes bounce existent déjà. Migration non nécessaire.")
        conn.close()
        return True

    print("Colonnes à ajouter :")
    for name, definition in to_add:
        print(f"  - {name} {definition}")

    if dry_run:
        print("\n[DRY-RUN] Aucune modification effectuée.")
        conn.close()
        return True

    backup_path = backup_db(db_path)
    print(f"Backup : {backup_path}")

    try:
        for name, definition in to_add:
            conn.execute(f"ALTER TABLE contact ADD COLUMN {name} {definition}")
            print(f"  + {name} ajoutée")
        conn.commit()
        print("Migration terminée avec succès.")
    except Exception as e:
        conn.rollback()
        print(f"ERREUR : {e}")
        conn.close()
        return False

    conn.close()
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Migration : ajout champs bounce contacts')
    parser.add_argument('--db', default=DEFAULT_DB)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    sys.exit(0 if migrate(args.db, dry_run=args.dry_run) else 1)
