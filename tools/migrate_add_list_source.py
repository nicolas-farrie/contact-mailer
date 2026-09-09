#!/usr/bin/env python3
"""
Migration — source externe d'une liste (`list_source`).

Crée la table `list_source(liste_id, provider, instance, ref, label, last_sync_at,
last_error, created_at)` : désigne la source qui alimente une liste, dont le contenu
devient alors un reflet. Générique — `provider` est l'identifiant d'un connecteur, jamais
un nom en dur : NOÉ aujourd'hui, les groupes Seafile ou les rôles BookStack demain, sans
migration supplémentaire. Aucune donnée à backfiller : les listes existantes restent
libres, sans source.

`UNIQUE(liste_id)` traduit un invariant de conception, pas une restriction provisoire :
deux sources signifieraient deux maîtres, et aucune règle de retrait ne pourrait trancher
le cas « présent dans l'une, absent de l'autre ».

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_list_source.py --dry-run
    python tools/migrate_add_list_source.py
    python tools/migrate_add_list_source.py --db data/contacts.db
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
CREATE TABLE IF NOT EXISTS list_source (
    id INTEGER PRIMARY KEY,
    liste_id INTEGER NOT NULL UNIQUE,
    provider VARCHAR(30) NOT NULL,
    instance VARCHAR(200) NOT NULL DEFAULT '',
    ref VARCHAR(200) NOT NULL,
    label VARCHAR(200) NOT NULL DEFAULT '',
    last_sync_at DATETIME,
    last_error VARCHAR(500),
    created_at DATETIME,
    FOREIGN KEY(liste_id) REFERENCES liste(id)
)
"""
INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_list_source_liste_id ON list_source(liste_id)",
    # « Quelle liste reflète ce groupe ? », posée à chaque synchronisation.
    "CREATE INDEX IF NOT EXISTS ix_list_source_lookup ON list_source(provider, instance, ref)",
]


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        need = not _has_table(conn, 'list_source')
        print(f"Base : {path}")
        print(f"  table list_source : {'à créer' if need else 'présente'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not need:
            for sql in INDEXES:
                conn.execute(sql)
            conn.commit()
            print("Rien à faire (table déjà présente). Index assurés.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute(CREATE)
        for sql in INDEXES:
            conn.execute(sql)
        conn.commit()
        print("✓ Migration appliquée. Table list_source créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
