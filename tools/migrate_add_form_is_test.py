#!/usr/bin/env python3
"""
Migration — flag `is_test` sur les données de formulaire (retours rc2).

Ajoute une colonne `is_test` (BOOLEAN, défaut 0) sur :
- `preference_response` : réponse issue d'un envoi TEST (« Envoi un test »),
- `field_proposal`      : proposition de fiche issue d'un envoi test.

But : un test suit le parcours réel (OTP compris) mais ses données sont exclues
partout où « réel » compte (verrou de structure, compteurs, export, « À valider »)
→ tester un formulaire ne le verrouille plus et ne pollue plus rien.

Non destructif : ajout de colonnes uniquement. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_form_is_test.py --dry-run
    python tools/migrate_add_form_is_test.py
    python tools/migrate_add_form_is_test.py --db data/contacts.db
"""
import sqlite3
import shutil
import sys
from datetime import datetime


def _cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _has_table(conn, name):
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        targets = []
        for table in ('preference_response', 'field_proposal'):
            if not _has_table(conn, table):
                print(f"  {table:22} : table absente (ignorée)")
                continue
            need = 'is_test' not in _cols(conn, table)
            print(f"  {table}.is_test{'':6} : {'à ajouter' if need else 'présente'}")
            if need:
                targets.append(table)

        print(f"Base : {path}")
        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not targets:
            print("Rien à faire (colonnes déjà présentes).")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        for table in targets:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN is_test BOOLEAN NOT NULL DEFAULT 0")
        conn.commit()
        print(f"✓ Migration appliquée. Colonne is_test ajoutée sur : {', '.join(targets)}.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
