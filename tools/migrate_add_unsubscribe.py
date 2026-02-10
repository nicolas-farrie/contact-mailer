#!/usr/bin/env python3
"""
Migration : ajout des champs de désabonnement aux contacts.

Usage :
    python tools/migrate_add_unsubscribe.py                    # migration réelle
    python tools/migrate_add_unsubscribe.py --dry-run          # simulation sans modification
    python tools/migrate_add_unsubscribe.py --db data/other.db # base personnalisée

Le script :
1. Crée un backup automatique de la base
2. ALTER TABLE contact ADD COLUMN is_unsubscribed BOOLEAN DEFAULT 0
3. ALTER TABLE contact ADD COLUMN unsubscribed_at DATETIME
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


def get_existing_columns(conn):
    """Retourne la liste des colonnes de la table contact."""
    cursor = conn.execute("PRAGMA table_info(contact)")
    return [row[1] for row in cursor.fetchall()]


def migrate(db_path, dry_run=False):
    """Exécute la migration."""
    if not os.path.exists(db_path):
        print(f"ERREUR : base introuvable : {db_path}")
        return False

    conn = sqlite3.connect(db_path)
    columns = get_existing_columns(conn)

    needs_is_unsubscribed = 'is_unsubscribed' not in columns
    needs_unsubscribed_at = 'unsubscribed_at' not in columns

    if not needs_is_unsubscribed and not needs_unsubscribed_at:
        print("Les colonnes is_unsubscribed et unsubscribed_at existent deja. Migration non necessaire.")
        conn.close()
        return True

    print(f"Colonnes a ajouter :")
    if needs_is_unsubscribed:
        print(f"  - is_unsubscribed BOOLEAN DEFAULT 0")
    if needs_unsubscribed_at:
        print(f"  - unsubscribed_at DATETIME")

    if dry_run:
        print("\n[DRY-RUN] Aucune modification effectuee.")
        conn.close()
        return True

    # Backup
    backup_path = backup_db(db_path)
    print(f"Backup : {backup_path}")

    try:
        if needs_is_unsubscribed:
            conn.execute("ALTER TABLE contact ADD COLUMN is_unsubscribed BOOLEAN DEFAULT 0")
            print("  + is_unsubscribed ajoutee")

        if needs_unsubscribed_at:
            conn.execute("ALTER TABLE contact ADD COLUMN unsubscribed_at DATETIME")
            print("  + unsubscribed_at ajoutee")

        conn.commit()
        print("Migration terminee avec succes.")

    except Exception as e:
        conn.rollback()
        print(f"ERREUR lors de la migration : {e}")
        conn.close()
        return False

    conn.close()
    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migration : ajout champs desabonnement')
    parser.add_argument('--db', default=DEFAULT_DB, help=f'Chemin de la base SQLite (defaut: {DEFAULT_DB})')
    parser.add_argument('--dry-run', action='store_true', help='Simulation sans modification')

    args = parser.parse_args()
    success = migrate(args.db, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
