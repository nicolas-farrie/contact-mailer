#!/usr/bin/env python3
"""
Migration : ajout de la colonne is_archived à preference_form (archivage des formulaires).

Usage :
    python tools/migrate_add_form_archive.py                    # migration réelle
    python tools/migrate_add_form_archive.py --dry-run          # simulation
    python tools/migrate_add_form_archive.py --db data/other.db # base personnalisée

Le script :
1. Crée un backup automatique de la base (data/contacts.db.bak.YYYYMMDD_HHMMSS)
2. Ajoute la colonne is_archived (BOOLEAN NOT NULL DEFAULT 0) via ALTER TABLE
3. Est idempotent (ne fait rien si la colonne existe déjà)
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


def already_migrated(conn):
    cursor = conn.execute("PRAGMA table_info(preference_form)")
    columns = [row[1] for row in cursor.fetchall()]
    return 'is_archived' in columns


def migrate(db_path, dry_run=False):
    if not os.path.exists(db_path):
        print(f"ERREUR : base introuvable : {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    try:
        if already_migrated(conn):
            print("Colonne is_archived déjà présente : rien à faire.")
            return True

        if dry_run:
            print("[DRY-RUN] Ajouterait : ALTER TABLE preference_form ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0")
            return True

        backup_path = backup_db(db_path)
        print(f"Backup : {backup_path}")

        conn.execute("ALTER TABLE preference_form ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0")
        conn.commit()
        print("Migration OK : colonne is_archived ajoutée à preference_form.")
        return True
    finally:
        conn.close()


if __name__ == '__main__':
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    db_path = DEFAULT_DB
    if '--db' in args:
        db_path = args[args.index('--db') + 1]
    ok = migrate(db_path, dry_run=dry_run)
    sys.exit(0 if ok else 1)
