#!/usr/bin/env python3
"""
Migration : ajout de User.moderation_signature (pseudonyme public de modération).

Signature libre, optionnelle, distincte du nom réel : affichée en pied des
diffusions modérées par cet utilisateur (contexte confidentialité / militants).

Usage :
    python tools/migrate_add_moderation_signature.py --dry-run
    python tools/migrate_add_moderation_signature.py
    python tools/migrate_add_moderation_signature.py --db data/contacts.db
"""
import sqlite3
import shutil
import sys
from datetime import datetime


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        cols = [r[1] for r in conn.execute('PRAGMA table_info(user)').fetchall()]
        if 'moderation_signature' in cols:
            print('✓ Colonne user.moderation_signature déjà présente — rien à faire.')
            return
        print(f"Base : {path}")
        print('  user.moderation_signature : à ajouter')
        if dry_run:
            print('(--dry-run : aucune écriture)')
            return
        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f'→ Sauvegarde : {backup}')
        conn.execute('ALTER TABLE user ADD COLUMN moderation_signature VARCHAR(120)')
        conn.commit()
        print('✓ Colonne ajoutée.')
    finally:
        conn.close()


if __name__ == '__main__':
    main()
