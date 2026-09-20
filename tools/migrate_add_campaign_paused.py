#!/usr/bin/env python3
"""
Migration — pause d'une campagne (`mail_campaign.paused`).

Ajoute la colonne `paused BOOLEAN NOT NULL DEFAULT 0` : une campagne en pause garde ses
mails en file mais aucun envoi ne les traite, ni le timer ni « Envoyer maintenant ».
Toutes les campagnes existantes sont actives (0), donc rien à backfiller.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_campaign_paused.py --dry-run
    python tools/migrate_add_campaign_paused.py
    python tools/migrate_add_campaign_paused.py --db data/contacts.db
"""
import sqlite3
import shutil
import sys
from datetime import datetime


def _has_column(conn, table, column):
    return column in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        need = not _has_column(conn, 'mail_campaign', 'paused')
        print(f"Base : {path}")
        print(f"  colonne mail_campaign.paused : {'à ajouter' if need else 'présente'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not need:
            print("Rien à faire (colonne déjà présente).")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute("ALTER TABLE mail_campaign ADD COLUMN paused BOOLEAN NOT NULL DEFAULT 0")
        conn.commit()
        print("✓ Migration appliquée. Colonne mail_campaign.paused créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
