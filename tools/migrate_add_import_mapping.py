#!/usr/bin/env python3
"""
Migration — mappings d'import réutilisables (`import_mapping`).

Crée la table `import_mapping(name, mapping JSON, created_at, created_by_id)` :
mémorise une association colonnes→champs pour la rejouer sur un fichier au même
format (import v2). Aucune donnée à backfiller.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_import_mapping.py --dry-run
    python tools/migrate_add_import_mapping.py
    python tools/migrate_add_import_mapping.py --db data/contacts.db
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
CREATE TABLE IF NOT EXISTS import_mapping (
    id INTEGER PRIMARY KEY,
    name VARCHAR(120) NOT NULL UNIQUE,
    mapping JSON NOT NULL,
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
        need = not _has_table(conn, 'import_mapping')
        print(f"Base : {path}")
        print(f"  table import_mapping : {'à créer' if need else 'présente'}")

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
        print("✓ Migration appliquée. Table import_mapping créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
