#!/usr/bin/env python3
"""
Migration : nom du mailing (distinct de l'objet de l'email).

- ADD COLUMN mail_campaign.name (VARCHAR 200)

Le nom sert d'identité lisible de la campagne (affiché dans le bandeau du parcours
d'envoi et dans les listes) ; l'objet reste le sujet de l'email. Sans nom, on
retombe sur l'objet.

Usage :
    python tools/migrate_add_campaign_name.py --dry-run
    python tools/migrate_add_campaign_name.py
    python tools/migrate_add_campaign_name.py --db data/contacts.db
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
            "SELECT name FROM sqlite_master WHERE type='table' AND name='mail_campaign'"
        ).fetchone() is not None
        if not has_table:
            print("Table mail_campaign absente (rien à faire).")
            return

        add = 'name' not in _cols(conn, 'mail_campaign')
        print(f"Base : {path}")
        print(f"  mail_campaign.name : {'à ajouter' if add else 'présent'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not add:
            print("✓ Rien à faire.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute("ALTER TABLE mail_campaign ADD COLUMN name VARCHAR(200)")
        conn.commit()
        print("✓ Migration appliquée. Colonne ajoutée : name")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
