#!/usr/bin/env python3
"""
Migration — champ personnalisé piloté par un connecteur (`custom_field_definition.synced_from`).

Un champ piloté est le REFLET de ce que dit le service source (NOÉ…) : ce qu'il y
répond remplace ce que nous avons, vide compris — un bénévole qui retire une compétence
dans NOÉ doit la voir disparaître ici. En contrepartie il ne se modifie plus dans la
fiche, mais dans le service. Les champs existants restent libres (NULL).

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_field_synced_from.py --dry-run
    python tools/migrate_add_field_synced_from.py
    python tools/migrate_add_field_synced_from.py --db data/contacts.db
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
        need = not _has_column(conn, 'custom_field_definition', 'synced_from')
        print(f"Base : {path}")
        print(f"  colonne custom_field_definition.synced_from : {'à ajouter' if need else 'présente'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not need:
            print("Rien à faire (colonne déjà présente).")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute("ALTER TABLE custom_field_definition ADD COLUMN synced_from VARCHAR(30)")
        conn.commit()
        print("✓ Migration appliquée. Colonne custom_field_definition.synced_from créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
