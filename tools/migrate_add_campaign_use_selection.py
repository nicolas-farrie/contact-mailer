#!/usr/bin/env python3
"""
Migration : `mail_campaign.use_selection` (BOOLEAN).

Quand vrai, la campagne unionne la « sélection courante » de son auteur aux
destinataires des listes cochées (cf. ContactSet / sélection courante S2). Nécessaire
pour que le choix survive au round-trip compose → confirmation → mise en file (le
template est rechargé depuis la base).

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_campaign_use_selection.py --dry-run
    python tools/migrate_add_campaign_use_selection.py
    python tools/migrate_add_campaign_use_selection.py --db data/contacts.db
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

        add = 'use_selection' not in _cols(conn, 'mail_campaign')
        print(f"Base : {path}")
        print(f"  mail_campaign.use_selection : {'à ajouter' if add else 'présent'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not add:
            print("✓ Rien à faire.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute("ALTER TABLE mail_campaign ADD COLUMN use_selection BOOLEAN DEFAULT 0")
        conn.commit()
        print("✓ Migration appliquée. Colonne ajoutée : use_selection")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
