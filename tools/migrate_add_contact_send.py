#!/usr/bin/env python3
"""
Migration — journal d'envoi par contact (`contact_send`), socle « Sélection & Segments ».

Crée la table `contact_send(contact_id, campaign_id, sent_at)` : une ligne par email
effectivement ENVOYÉ à un contact. Débloque les segments « jamais mailé » / « déjà reçu
la campagne X » et l'historique d'envoi par contact — de façon propre et portable
(pas de matching dans le JSON de `mail_queue_item`).

Backfill : reconstruit l'historique depuis `mail_queue_item` (status='sent'), en lisant
l'`id` du contact dans le snapshot JSON. Ne backfill QUE si la table vient d'être créée
(idempotent). Les snapshots dont le contact n'existe plus sont ignorés.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_contact_send.py --dry-run
    python tools/migrate_add_contact_send.py
    python tools/migrate_add_contact_send.py --db data/contacts.db
"""
import sqlite3
import json
import shutil
import sys
from datetime import datetime, timezone


def _has_table(conn, name):
    return conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


CREATE = """
CREATE TABLE IF NOT EXISTS contact_send (
    id INTEGER PRIMARY KEY,
    contact_id INTEGER NOT NULL,
    campaign_id VARCHAR(255) NOT NULL,
    sent_at DATETIME NOT NULL,
    FOREIGN KEY(contact_id) REFERENCES contact(id)
)
"""
IDX_CONTACT = "CREATE INDEX IF NOT EXISTS ix_contact_send_contact_id ON contact_send(contact_id)"
IDX_CAMPAIGN = "CREATE INDEX IF NOT EXISTS ix_contact_send_campaign_id ON contact_send(campaign_id)"


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        need = not _has_table(conn, 'contact_send')
        print(f"Base : {path}")
        print(f"  table contact_send : {'à créer' if need else 'présente'}")

        # Prévisualiser le backfill (nombre d'items 'sent' rattachables à un contact existant)
        backfill_n = 0
        if _has_table(conn, 'mail_queue_item') and _has_table(conn, 'contact'):
            valid = {r[0] for r in conn.execute("SELECT id FROM contact").fetchall()}
            for (snap, cid_, sent_at) in conn.execute(
                    "SELECT contact, campaign_id, sent_at FROM mail_queue_item WHERE status='sent'"):
                try:
                    d = json.loads(snap) if isinstance(snap, str) else (snap or {})
                except Exception:
                    d = {}
                if d.get('id') in valid and cid_:
                    backfill_n += 1
        print(f"  backfill depuis l'historique : {backfill_n} envoi(s) rattachable(s)")

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not need:
            print("Rien à faire (table déjà présente — backfill non rejoué).")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        conn.execute(CREATE)
        conn.execute(IDX_CONTACT)
        conn.execute(IDX_CAMPAIGN)

        inserted = 0
        if _has_table(conn, 'mail_queue_item') and _has_table(conn, 'contact'):
            valid = {r[0] for r in conn.execute("SELECT id FROM contact").fetchall()}
            now = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            for (snap, cid_, sent_at) in conn.execute(
                    "SELECT contact, campaign_id, sent_at FROM mail_queue_item WHERE status='sent'"):
                try:
                    d = json.loads(snap) if isinstance(snap, str) else (snap or {})
                except Exception:
                    d = {}
                cid = d.get('id')
                if cid in valid and cid_:
                    conn.execute(
                        "INSERT INTO contact_send (contact_id, campaign_id, sent_at) VALUES (?, ?, ?)",
                        (cid, cid_, sent_at or now))
                    inserted += 1

        conn.commit()
        print(f"✓ Migration appliquée. Table contact_send créée + {inserted} envoi(s) backfillé(s).")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
