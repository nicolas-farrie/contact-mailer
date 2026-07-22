#!/usr/bin/env python3
"""
Migration : champs de gestion des listes.

- ADD COLUMN liste.is_archived   (Boolean, défaut 0)  -> archivage réversible
- ADD COLUMN liste.color         (VARCHAR, hex '#rrggbb') -> pastille choisie
- ADD COLUMN liste.created_by_id (Integer, FK user.id soft) -> propriétaire/créateur
  (posé dès maintenant, sera exploité plus tard : filtre « mes listes »)

Usage :
    python tools/migrate_add_liste_fields.py --dry-run
    python tools/migrate_add_liste_fields.py
    python tools/migrate_add_liste_fields.py --db data/contacts.db
"""
import sqlite3
import shutil
import sys
from datetime import datetime


def _cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        cols = _cols(conn, 'liste')
        adds = {
            'is_archived': "ALTER TABLE liste ADD COLUMN is_archived BOOLEAN DEFAULT 0 NOT NULL",
            'color': "ALTER TABLE liste ADD COLUMN color VARCHAR(9)",
            'created_by_id': "ALTER TABLE liste ADD COLUMN created_by_id INTEGER",
        }
        todo = {c: sql for c, sql in adds.items() if c not in cols}

        print(f"Base : {path}")
        for c in adds:
            print(f"  liste.{c:<14}: {'à ajouter' if c in todo else 'présent'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not todo:
            print("✓ Rien à faire.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        for c, sql in todo.items():
            conn.execute(sql)
        conn.commit()
        print(f"✓ Migration appliquée. Colonnes ajoutées : {', '.join(todo)}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
