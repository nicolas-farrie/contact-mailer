#!/usr/bin/env python3
"""
Migration M9 — Formulaires v2 (OTP + pré-remplissage, Phase 2).

Crée la table `form_access_code` : code à usage unique (OTP) sécurisant le
pré-remplissage d'un formulaire contenant un bloc « fiche ». Le code n'est JAMAIS
transmis dans le mail du lien — il est envoyé à la demande, à l'ouverture de la page
publique, et seul son hash est stocké.

Non destructif : nouvelle table uniquement, aucun impact sur l'existant.

Usage :
    python tools/migrate_add_form_access_code.py --dry-run
    python tools/migrate_add_form_access_code.py
    python tools/migrate_add_form_access_code.py --db data/contacts.db
"""
import sqlite3
import shutil
import sys
from datetime import datetime


def _has_table(conn, name):
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


CREATE_FORM_ACCESS_CODE = """
CREATE TABLE IF NOT EXISTS form_access_code (
    id INTEGER PRIMARY KEY,
    form_id INTEGER NOT NULL,
    contact_uid VARCHAR(64) NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL,
    expires_at DATETIME NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    consumed BOOLEAN NOT NULL DEFAULT 0,
    FOREIGN KEY(form_id) REFERENCES preference_form(id)
)
"""

CREATE_IDX_FORM = "CREATE INDEX IF NOT EXISTS ix_form_access_code_form_id ON form_access_code(form_id)"
CREATE_IDX_UID = "CREATE INDEX IF NOT EXISTS ix_form_access_code_contact_uid ON form_access_code(contact_uid)"


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        if not _has_table(conn, 'preference_form'):
            print("Table preference_form absente (rien à faire).")
            return

        need = not _has_table(conn, 'form_access_code')
        print(f"Base : {path}")
        print(f"  table form_access_code : {'à créer' if need else 'présente'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not need:
            print("Rien à faire (table déjà présente).")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute(CREATE_FORM_ACCESS_CODE)
        conn.execute(CREATE_IDX_FORM)
        conn.execute(CREATE_IDX_UID)
        conn.commit()
        print("✓ Migration appliquée. Table form_access_code créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
