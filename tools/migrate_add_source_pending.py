#!/usr/bin/env python3
"""
Migration — nouveaux venus en attente d'import (`list_source.pending_count`).

La synchronisation compte depuis toujours les membres d'une source externe qui n'ont
aucune fiche appariée — des bénévoles inscrits après le premier import. Ce compte
n'allait nulle part : il s'affichait dans la sortie de `tools/sync_lists.py`, donc dans
les logs du timer, que personne ne lit. La colonne le conserve pour que l'interface
puisse dire « 7 à examiner » sur la liste concernée.

Colonne `pending_count INTEGER NOT NULL DEFAULT 0` : les sources existantes repartent de
0 et seront renseignées à leur prochaine synchronisation. Rien à backfiller.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_source_pending.py --dry-run
    python tools/migrate_add_source_pending.py
    python tools/migrate_add_source_pending.py --db data/contacts.db
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
        need = not _has_column(conn, 'list_source', 'pending_count')
        print(f"Base : {path}")
        print(f"  colonne list_source.pending_count : {'à ajouter' if need else 'présente'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not need:
            print("Rien à faire (colonne déjà présente).")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute("ALTER TABLE list_source ADD COLUMN pending_count INTEGER NOT NULL DEFAULT 0")
        conn.commit()
        print("✓ Migration appliquée. Colonne list_source.pending_count créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
