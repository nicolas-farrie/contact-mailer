#!/usr/bin/env python3
"""
Migration — modèles de mailing (`mail_template`).

Crée la table `mail_template(name, subject, body, format, reply_to, signed,
created_by_id, created_at, updated_at)` : des contenus de mailing réutilisables et
partagés, distincts des campagnes (qu'un envoi consomme). Aucune donnée à backfiller.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_mail_template.py --dry-run
    python tools/migrate_add_mail_template.py
    python tools/migrate_add_mail_template.py --db data/contacts.db
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
CREATE TABLE IF NOT EXISTS mail_template (
    id INTEGER PRIMARY KEY,
    name VARCHAR(200) NOT NULL UNIQUE,
    subject TEXT DEFAULT '',
    body TEXT DEFAULT '',
    format VARCHAR(10) DEFAULT 'html',
    reply_to VARCHAR(200),
    signed BOOLEAN NOT NULL DEFAULT 0,
    created_by_id INTEGER,
    created_at DATETIME,
    updated_at DATETIME,
    FOREIGN KEY(created_by_id) REFERENCES user(id)
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
        need = not _has_table(conn, 'mail_template')
        print(f"Base : {path}")
        print(f"  table mail_template : {'à créer' if need else 'présente'}")

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
        print("✓ Migration appliquée. Table mail_template créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
