#!/usr/bin/env python3
"""
Migration — anti-doublon des notifications de demandes de diffusion
(`notified_submission`).

Crée la table `notified_submission(message_id PK, notified_at)` : mémorise les
demandes déjà notifiées aux modérateurs (par `Message-ID`) pour ne pas ré-alerter
au re-scan. Aucune donnée à backfiller.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_notified_submission.py --dry-run
    python tools/migrate_add_notified_submission.py
    python tools/migrate_add_notified_submission.py --db data/contacts.db
"""
import sqlite3
import shutil
import sys
from datetime import datetime


def _has_table(conn, name):
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


CREATE = """
CREATE TABLE IF NOT EXISTS notified_submission (
    message_id VARCHAR(500) PRIMARY KEY,
    notified_at DATETIME
)
"""


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        need = not _has_table(conn, 'notified_submission')
        print(f"Base : {path}")
        print(f"  table notified_submission : {'à créer' if need else 'présente'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not need:
            print("Rien à faire (table déjà présente).")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute(CREATE)
        conn.commit()
        print("✓ Migration appliquée. Table notified_submission créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
