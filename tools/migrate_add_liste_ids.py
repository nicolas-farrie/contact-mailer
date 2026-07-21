#!/usr/bin/env python3
"""
Migration : multi-listes sur les campagnes (dédoublonnage à l'envoi).

- ADD COLUMN mail_campaign.liste_ids (JSON, stocké en TEXT par SQLite)
- Backfill : pour chaque campagne ayant déjà un liste_id, liste_ids = [liste_id].

Usage :
    python tools/migrate_add_liste_ids.py --dry-run
    python tools/migrate_add_liste_ids.py
    python tools/migrate_add_liste_ids.py --db data/contacts.db
"""
import json
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

        cols = _cols(conn, 'mail_campaign')
        add_col = 'liste_ids' not in cols
        print(f"Base : {path}")
        print(f"  mail_campaign.liste_ids : {'à ajouter' if add_col else 'présent'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not add_col:
            print("✓ Rien à faire.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute("ALTER TABLE mail_campaign ADD COLUMN liste_ids TEXT")

        # Backfill : liste_ids = [liste_id] pour les campagnes existantes
        rows = conn.execute(
            "SELECT id, liste_id FROM mail_campaign WHERE liste_id IS NOT NULL"
        ).fetchall()
        for cid, lid in rows:
            conn.execute("UPDATE mail_campaign SET liste_ids = ? WHERE id = ?",
                         (json.dumps([lid]), cid))

        conn.commit()
        print(f"✓ Migration appliquée. Campagnes backfillées : {len(rows)}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
