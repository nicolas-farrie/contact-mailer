#!/usr/bin/env python3
"""
Migration : ajout des champs genre et titre aux contacts.

Usage :
    python tools/migrate_add_genre_titre.py                    # migration réelle
    python tools/migrate_add_genre_titre.py --dry-run          # simulation sans modification
    python tools/migrate_add_genre_titre.py --db data/other.db # base personnalisée
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
    if 'genre' not in columns:
        to_add.append(('genre', 'VARCHAR(20)'))
    if 'titre' not in columns:
        to_add.append(('titre', 'VARCHAR(50)'))

    if not to_add:
        print("Les colonnes genre et titre existent déjà. Migration non nécessaire.")
        conn.close()
        return True

    for col, coltype in to_add:
        print(f"Colonne à ajouter : {col} {coltype}")

    if dry_run:
        print("\n[DRY-RUN] Aucune modification effectuée.")
        conn.close()
        return True

    backup_path = backup_db(db_path)
    print(f"Backup : {backup_path}")

    try:
        for col, coltype in to_add:
            conn.execute(f"ALTER TABLE contact ADD COLUMN {col} {coltype}")
            print(f"  + {col} ajoutée")
        conn.commit()
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

    parser = argparse.ArgumentParser(description='Migration : ajout champs genre et titre')
    parser.add_argument('--db', default=DEFAULT_DB, help=f'Chemin de la base SQLite (défaut: {DEFAULT_DB})')
    parser.add_argument('--dry-run', action='store_true', help='Simulation sans modification')

    args = parser.parse_args()
    success = migrate(args.db, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
