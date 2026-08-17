#!/usr/bin/env python3
"""
Migration — membres d'un ContactSet (`contact_set_member`).

Crée la table générique `contact_set_member(set_key, contact_id, added_at)` avec PK
composite (set_key, contact_id) : socle de la « sélection courante » (clé `user:<id>`)
et d'autres ensembles de contacts instanciés en code (cf. classe ContactSet). Aucune
donnée à backfiller.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_contact_set_member.py --dry-run
    python tools/migrate_add_contact_set_member.py
    python tools/migrate_add_contact_set_member.py --db data/contacts.db
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
CREATE TABLE IF NOT EXISTS contact_set_member (
    set_key VARCHAR(80) NOT NULL,
    contact_id INTEGER NOT NULL,
    added_at DATETIME,
    PRIMARY KEY (set_key, contact_id),
    FOREIGN KEY(contact_id) REFERENCES contact(id)
)
"""

# PK composite (set_key, contact_id) → index naturel sur le préfixe set_key.
# Un index dédié sur contact_id sert le cas « à quels ensembles appartient ce contact ».
INDEX = "CREATE INDEX IF NOT EXISTS ix_contact_set_member_contact ON contact_set_member(contact_id)"


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        need = not _has_table(conn, 'contact_set_member')
        print(f"Base : {path}")
        print(f"  table contact_set_member : {'à créer' if need else 'présente'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not need:
            # La table peut exister sans l'index (create_all ne crée pas l'index nommé) : on l'assure.
            conn.execute(INDEX)
            conn.commit()
            print("Rien à faire (table déjà présente). Index assuré.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute(CREATE)
        conn.execute(INDEX)
        conn.commit()
        print("✓ Migration appliquée. Table contact_set_member créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
