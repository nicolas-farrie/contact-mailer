#!/usr/bin/env python3
"""
Migration — segments nommés (`contact_segment`).

Crée la table `contact_segment(name, conditions JSON, join, created_at, created_by_id)` :
définition réutilisable d'un filtre avancé (P4b des filtres avancés). Aucune donnée à
backfiller.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_contact_segment.py --dry-run
    python tools/migrate_add_contact_segment.py
    python tools/migrate_add_contact_segment.py --db data/contacts.db
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
CREATE TABLE IF NOT EXISTS contact_segment (
    id INTEGER PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    conditions JSON NOT NULL,
    join_mode VARCHAR(4) DEFAULT 'and',
    created_at DATETIME,
    created_by_id INTEGER,
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
        need = not _has_table(conn, 'contact_segment')
        print(f"Base : {path}")
        print(f"  table contact_segment : {'à créer' if need else 'présente'}")

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
        print("✓ Migration appliquée. Table contact_segment créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
