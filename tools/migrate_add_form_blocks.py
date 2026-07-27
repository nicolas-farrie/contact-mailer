#!/usr/bin/env python3
"""
Migration M1 — Formulaires v2 (assembleur de blocs).

Crée le socle de données de l'assembleur :
- Table `form_block`      : bloc typé d'un formulaire (listes | sondage | fiche), ordonné, + config JSON.
- Table `survey_question` : questions d'un bloc « sondage » (hors base, stockage isolé).
- Table `field_proposal`  : modifications proposées par un contact via un bloc « fiche »
                            (file « À valider » ; rien n'est écrit sur la fiche avant validation admin).
- Colonne `preference_response.data`      (JSON) : payload d'une réponse (listes + sondage).
- Colonne `preference_form_liste.block_id` (FK) : rattache les listes à leur bloc.
- Backfill : pour chaque formulaire existant ayant des listes, crée un bloc `listes` (ordre 0)
             et y rattache ses `preference_form_liste`.

Non destructif : `form.listes` (par form_id) continue de fonctionner ; block_id est additionnel.

Usage :
    python tools/migrate_add_form_blocks.py --dry-run
    python tools/migrate_add_form_blocks.py
    python tools/migrate_add_form_blocks.py --db data/contacts.db
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


CREATE_FORM_BLOCK = """
CREATE TABLE IF NOT EXISTS form_block (
    id INTEGER PRIMARY KEY,
    form_id INTEGER NOT NULL,
    type VARCHAR(20) NOT NULL,
    ordre INTEGER DEFAULT 0,
    config JSON,
    FOREIGN KEY(form_id) REFERENCES preference_form(id)
)
"""

CREATE_SURVEY_QUESTION = """
CREATE TABLE IF NOT EXISTS survey_question (
    id INTEGER PRIMARY KEY,
    block_id INTEGER NOT NULL,
    ordre INTEGER DEFAULT 0,
    label VARCHAR(300) NOT NULL,
    type VARCHAR(20) DEFAULT 'texte_court',
    config JSON,
    FOREIGN KEY(block_id) REFERENCES form_block(id)
)
"""

CREATE_FIELD_PROPOSAL = """
CREATE TABLE IF NOT EXISTS field_proposal (
    id INTEGER PRIMARY KEY,
    form_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    field_key VARCHAR(64) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    otp_verified BOOLEAN NOT NULL DEFAULT 0,
    proposed_at DATETIME,
    reviewed_by_id INTEGER,
    reviewed_at DATETIME,
    FOREIGN KEY(form_id) REFERENCES preference_form(id),
    FOREIGN KEY(contact_id) REFERENCES contact(id),
    FOREIGN KEY(reviewed_by_id) REFERENCES user(id)
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
        if not _has_table(conn, 'preference_form'):
            print("Table preference_form absente (rien à faire).")
            return

        need_form_block = not _has_table(conn, 'form_block')
        need_survey = not _has_table(conn, 'survey_question')
        need_proposal = not _has_table(conn, 'field_proposal')
        need_resp_data = 'data' not in _cols(conn, 'preference_response')
        need_fl_block = 'block_id' not in _cols(conn, 'preference_form_liste')

        print(f"Base : {path}")
        print(f"  table form_block                    : {'à créer' if need_form_block else 'présente'}")
        print(f"  table survey_question               : {'à créer' if need_survey else 'présente'}")
        print(f"  table field_proposal                : {'à créer' if need_proposal else 'présente'}")
        print(f"  preference_response.data            : {'à ajouter' if need_resp_data else 'présente'}")
        print(f"  preference_form_liste.block_id      : {'à ajouter' if need_fl_block else 'présente'}")

        # formulaires à backfiller (ont des listes mais aucun bloc 'listes' encore)
        forms_to_backfill = []
        if not need_form_block:
            rows = conn.execute("""
                SELECT DISTINCT fl.form_id FROM preference_form_liste fl
                WHERE fl.form_id NOT IN (SELECT form_id FROM form_block WHERE type='listes')
            """).fetchall()
            forms_to_backfill = [r[0] for r in rows]
        else:
            rows = conn.execute("SELECT DISTINCT form_id FROM preference_form_liste").fetchall()
            forms_to_backfill = [r[0] for r in rows]
        print(f"  backfill bloc 'listes' pour          : {len(forms_to_backfill)} formulaire(s)")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute(CREATE_FORM_BLOCK)
        conn.execute(CREATE_SURVEY_QUESTION)
        conn.execute(CREATE_FIELD_PROPOSAL)
        if need_resp_data:
            conn.execute("ALTER TABLE preference_response ADD COLUMN data JSON")
        if need_fl_block:
            conn.execute("ALTER TABLE preference_form_liste ADD COLUMN block_id INTEGER")

        # Backfill : un bloc 'listes' par formulaire concerné, puis rattachement des listes.
        for form_id in forms_to_backfill:
            cur = conn.execute(
                "INSERT INTO form_block (form_id, type, ordre, config) VALUES (?, 'listes', 0, NULL)",
                (form_id,))
            block_id = cur.lastrowid
            conn.execute(
                "UPDATE preference_form_liste SET block_id=? WHERE form_id=? AND (block_id IS NULL)",
                (block_id, form_id))

        conn.commit()
        print(f"✓ Migration appliquée. Tables créées + colonnes ajoutées + "
              f"{len(forms_to_backfill)} bloc(s) 'listes' backfillé(s).")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
