#!/usr/bin/env python3
"""
Migration : `user.is_moderator` (BOOLEAN).

Marque les utilisateurs qui reçoivent les alertes de nouvelles demandes de diffusion
(cf. daemon de notification). Orthogonal au rôle admin. Défaut = False ; si personne
n'est flaggé, le notifieur retombe sur les admins (jamais d'alerte silencieuse).

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_user_is_moderator.py --dry-run
    python tools/migrate_add_user_is_moderator.py
    python tools/migrate_add_user_is_moderator.py --db data/contacts.db
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
            "SELECT name FROM sqlite_master WHERE type='table' AND name='user'"
        ).fetchone() is not None
        if not has_table:
            print("Table user absente (rien à faire).")
            return

        add = 'is_moderator' not in _cols(conn, 'user')
        print(f"Base : {path}")
        print(f"  user.is_moderator : {'à ajouter' if add else 'présent'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not add:
            print("✓ Rien à faire.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute("ALTER TABLE user ADD COLUMN is_moderator BOOLEAN DEFAULT 0 NOT NULL")
        conn.commit()
        print("✓ Migration appliquée. Colonne ajoutée : is_moderator")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
