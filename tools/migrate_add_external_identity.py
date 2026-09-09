#!/usr/bin/env python3
"""
Migration — identités externes (`external_identity`).

Crée la table `external_identity(contact_id, provider, instance, external_id,
created_at, updated_at)` : lien stable entre un contact et son identité dans un service
externe (NOÉ, Seafile, BookStack). Rend les resynchronisations idempotentes, là où
l'appariement par email ou par nom recrée des doublons dès qu'une personne change
d'adresse. Aucune donnée à backfiller — les liens se créent au premier appariement.

Table jointe plutôt qu'une colonne par service : un connecteur de plus ne demandera pas
de migration, et un contact peut porter plusieurs identités (deux projets NOÉ, ou NOÉ et
BookStack). `instance` distingue deux installations du même service.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_external_identity.py --dry-run
    python tools/migrate_add_external_identity.py
    python tools/migrate_add_external_identity.py --db data/contacts.db
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
CREATE TABLE IF NOT EXISTS external_identity (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL,
    provider VARCHAR(30) NOT NULL,
    instance VARCHAR(200) NOT NULL DEFAULT '',
    external_id VARCHAR(200) NOT NULL,
    created_at DATETIME,
    updated_at DATETIME,
    CONSTRAINT uq_external_identity_ref UNIQUE (provider, instance, external_id),
    FOREIGN KEY(contact_id) REFERENCES contact(id)
)
"""
INDEXES = [
    # Recherche « quelles identités pour ce contact ? » à l'affichage d'une fiche.
    "CREATE INDEX IF NOT EXISTS ix_external_identity_contact_id ON external_identity(contact_id)",
    # Recherche inverse « qui est ce bénévole ? », faite pour chaque ligne à chaque synchro.
    "CREATE INDEX IF NOT EXISTS ix_external_identity_lookup ON external_identity(provider, instance, external_id)",
]


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        need = not _has_table(conn, 'external_identity')
        print(f"Base : {path}")
        print(f"  table external_identity : {'à créer' if need else 'présente'}")

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
        print("✓ Migration appliquée. Table external_identity créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
