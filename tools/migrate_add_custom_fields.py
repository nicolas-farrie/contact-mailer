#!/usr/bin/env python3
"""
Migration : champs personnalisés + découplage identité / accord grammatical.

- ADD COLUMN contact.custom_fields   (JSON, stocké en TEXT par SQLite)
- ADD COLUMN contact.civilite        (identité / formule d'appel)
- CREATE TABLE custom_field_definition
- Normalise contact.genre en ACCORD grammatical (Madame/Mme/F → Féminin,
  Monsieur/Mr/M/H → Masculin, Inclusif/NB → Inclusif) ET copie l'identité
  d'origine (Madame/Monsieur) dans contact.civilite. La normalisation ne tourne
  QUE si la colonne civilite vient d'être ajoutée (idempotent).

Usage :
    python tools/migrate_add_custom_fields.py --dry-run
    python tools/migrate_add_custom_fields.py
    python tools/migrate_add_custom_fields.py --db data/contacts.db
"""
import sqlite3
import shutil
import sys
from datetime import datetime


def _cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _normalize(genre):
    """genre d'origine -> (civilite, accord)."""
    s = (genre or '').strip().lower()
    if s in ('madame', 'mme', 'mme.', 'mrs'):
        return 'Madame', 'Féminin'
    if s in ('monsieur', 'mr', 'mr.', 'm.'):
        return 'Monsieur', 'Masculin'
    if s in ('m', 'masculin', 'h', 'homme'):
        return '', 'Masculin'
    if s in ('f', 'féminin', 'feminin', 'femme'):
        return '', 'Féminin'
    if s in ('inclusif', 'neutre', 'nb', 'non-binaire', 'non binaire'):
        return '', 'Inclusif'
    return '', 'Inclusif'   # inconnu / vide -> accord inclusif par défaut (jamais vide → conditionnelles prévisibles)


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        cols = _cols(conn, 'contact')
        add_custom = 'custom_fields' not in cols
        add_civilite = 'civilite' not in cols
        has_cfd = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='custom_field_definition'"
        ).fetchone() is not None
        cfd_cols = _cols(conn, 'custom_field_definition') if has_cfd else []
        add_help = has_cfd and 'help_text' not in cfd_cols
        add_req = has_cfd and 'required' not in cfd_cols

        print(f"Base : {path}")
        print(f"  contact.custom_fields   : {'à ajouter' if add_custom else 'présent'}")
        print(f"  contact.civilite        : {'à ajouter' if add_civilite else 'présent'}")
        print(f"  custom_field_definition : {'à créer' if not has_cfd else 'présente'}")
        print(f"  cfd.help_text           : {'à ajouter' if add_help else ('inclus' if not has_cfd else 'présent')}")
        print(f"  cfd.required            : {'à ajouter' if add_req else ('inclus' if not has_cfd else 'présent')}")
        print(f"  normalisation genre→accord + civilite : {'OUI' if add_civilite else 'déjà fait (skip)'}")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not (add_custom or add_civilite or not has_cfd or add_help or add_req):
            print("✓ Rien à faire.")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        if add_custom:
            conn.execute("ALTER TABLE contact ADD COLUMN custom_fields TEXT")
        if add_civilite:
            conn.execute("ALTER TABLE contact ADD COLUMN civilite VARCHAR(40)")
        if not has_cfd:
            conn.execute("""
                CREATE TABLE custom_field_definition (
                    id INTEGER PRIMARY KEY,
                    key VARCHAR(64) NOT NULL UNIQUE,
                    display_name VARCHAR(200) NOT NULL,
                    type VARCHAR(20) DEFAULT 'text',
                    options TEXT,
                    help_text VARCHAR(300),
                    required BOOLEAN DEFAULT 0 NOT NULL,
                    ordre INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT 1 NOT NULL,
                    created_at DATETIME
                )
            """)
        else:
            if add_help:
                conn.execute("ALTER TABLE custom_field_definition ADD COLUMN help_text VARCHAR(300)")
            if add_req:
                conn.execute("ALTER TABLE custom_field_definition ADD COLUMN required BOOLEAN DEFAULT 0 NOT NULL")

        normalized = 0
        if add_civilite:
            rows = conn.execute("SELECT id, genre FROM contact").fetchall()
            for cid, genre in rows:
                civ, acc = _normalize(genre)
                conn.execute("UPDATE contact SET civilite = ?, genre = ? WHERE id = ?",
                             (civ, acc, cid))
                normalized += 1

        conn.commit()
        print(f"✓ Migration appliquée. Contacts normalisés : {normalized}")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
