#!/usr/bin/env python3
"""
Migration : création des tables de formulaires de préférences.

Usage :
    python tools/migrate_add_preferences.py
    python tools/migrate_add_preferences.py --dry-run
    python tools/migrate_add_preferences.py --db data/other.db
"""
import sqlite3
import sys
import os

DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'contacts.db')

TABLES = {
    'preference_form': """
        CREATE TABLE IF NOT EXISTS preference_form (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nom VARCHAR(200) NOT NULL,
            description TEXT,
            token VARCHAR(32) UNIQUE NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT 1,
            expires_at DATETIME,
            created_at DATETIME,
            created_by_id INTEGER REFERENCES user(id)
        )""",
    'preference_form_liste': """
        CREATE TABLE IF NOT EXISTS preference_form_liste (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            form_id INTEGER NOT NULL REFERENCES preference_form(id),
            liste_id INTEGER NOT NULL REFERENCES liste(id),
            label VARCHAR(200) NOT NULL,
            help_text TEXT,
            ordre INTEGER DEFAULT 0
        )""",
    'preference_response': """
        CREATE TABLE IF NOT EXISTS preference_response (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            contact_id INTEGER NOT NULL REFERENCES contact(id),
            form_id INTEGER NOT NULL REFERENCES preference_form(id),
            submitted_at DATETIME
        )""",
}


def migrate(db_path, dry_run=False):
    if not os.path.exists(db_path):
        print(f"ERREUR : base introuvable : {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    existing = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}

    to_create = [name for name in TABLES if name not in existing]
    if not to_create:
        print("Les tables de préférences existent déjà. Migration non nécessaire.")
        conn.close()
        return True

    print("Tables à créer :", ', '.join(to_create))
    if dry_run:
        print("\n[DRY-RUN] Aucune modification effectuée.")
        conn.close()
        return True

    try:
        for name in to_create:
            conn.execute(TABLES[name])
            print(f"  + {name} créée")
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
    parser = argparse.ArgumentParser(description='Migration : tables formulaires de préférences')
    parser.add_argument('--db', default=DEFAULT_DB)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    sys.exit(0 if migrate(args.db, dry_run=args.dry_run) else 1)
