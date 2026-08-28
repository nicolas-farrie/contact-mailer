#!/usr/bin/env python3
"""
Migration : `mail_campaign.reply_to` (VARCHAR).

Adresse de réponse (en-tête Reply-To) d'un mailing, distincte de la boîte d'envoi
(le From reste le domaine authentifié). Cas d'usage : courrier envoyé depuis
`...@asso34.fr` mais réponses souhaitées chez la tête de liste.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_campaign_reply_to.py --dry-run
    python tools/migrate_add_campaign_reply_to.py
    python tools/migrate_add_campaign_reply_to.py --db data/contacts.db
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

        add = 'reply_to' not in _cols(conn, 'mail_campaign')
        print(f"Base : {path}")
        print(f"  mail_campaign.reply_to : {'à ajouter' if add else 'présent'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not add:
            print("✓ Rien à faire.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute("ALTER TABLE mail_campaign ADD COLUMN reply_to VARCHAR(200)")
        conn.commit()
        print("✓ Migration appliquée. Colonne ajoutée : reply_to")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
