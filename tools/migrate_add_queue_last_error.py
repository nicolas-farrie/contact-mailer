#!/usr/bin/env python3
"""
Migration : trace durable de la dernière erreur d'envoi (`mail_queue_item.last_error`).

- ADD COLUMN mail_queue_item.last_error (TEXT)

`error` porte l'erreur de l'essai courant et est vidé au « retry » (reset_errors) ;
`last_error` la CONSERVE pour la forensique post-incident (survit à un retry).

Usage :
    python tools/migrate_add_queue_last_error.py --dry-run
    python tools/migrate_add_queue_last_error.py
    python tools/migrate_add_queue_last_error.py --db data/contacts.db
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
        has_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='mail_queue_item'"
        ).fetchone() is not None
        if not has_table:
            print("Table mail_queue_item absente (rien à faire).")
            return

        add = 'last_error' not in _cols(conn, 'mail_queue_item')
        print(f"Base : {path}")
        print(f"  mail_queue_item.last_error : {'à ajouter' if add else 'présent'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not add:
            print("✓ Rien à faire.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute("ALTER TABLE mail_queue_item ADD COLUMN last_error TEXT")
        conn.commit()
        print("✓ Migration appliquée. Colonne ajoutée : last_error")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
