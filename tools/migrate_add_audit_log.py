#!/usr/bin/env python3
"""
Migration — journal d'audit (`audit_log`).

Crée la table `audit_log(ts, user_id, username, action, target_type, target_id,
details JSON, ip)` : traçabilité sécurité & données personnelles (Tier 2). Aucune
donnée à backfiller.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_audit_log.py --dry-run
    python tools/migrate_add_audit_log.py
    python tools/migrate_add_audit_log.py --db data/contacts.db
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
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY,
    ts DATETIME,
    user_id INTEGER,
    username VARCHAR(120),
    action VARCHAR(50),
    target_type VARCHAR(50),
    target_id VARCHAR(100),
    details JSON,
    ip VARCHAR(64),
    FOREIGN KEY(user_id) REFERENCES user(id)
)
"""
INDEXES = [
    "CREATE INDEX IF NOT EXISTS ix_audit_log_ts ON audit_log(ts)",
    "CREATE INDEX IF NOT EXISTS ix_audit_log_action ON audit_log(action)",
]


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        need = not _has_table(conn, 'audit_log')
        print(f"Base : {path}")
        print(f"  table audit_log : {'à créer' if need else 'présente'}")

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
        print("✓ Migration appliquée. Table audit_log créée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
