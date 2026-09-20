#!/usr/bin/env python3
"""
Migration — reprise après refus temporaire et comptage du volume envoyé.

Deux colonnes, pour que l'envoi asynchrone survive aux limites de l'hébergeur :

- `mail_queue_item.deferred_until DATETIME NULL` : un refus TEMPORAIRE (4xx : plafond
  horaire, volume cumulé, serveur momentanément indisponible) laisse l'item EN ATTENTE
  avec une date de reprise, au lieu de le marquer en erreur définitive — sans quoi seul
  un clic humain pouvait le relancer.
- `contact_send.size_bytes INTEGER NULL` : taille réelle du message transmis (corps +
  pièces jointes encodées), pour le plafond de volume glissant. NULL sur les envois
  antérieurs, qui ne sont donc pas comptés dans le volume — sans effet passé une heure.

Non destructif. Idempotent, backup, dry-run.

Usage :
    python tools/migrate_add_send_backoff.py --dry-run
    python tools/migrate_add_send_backoff.py
    python tools/migrate_add_send_backoff.py --db data/contacts.db
"""
import sqlite3
import shutil
import sys
from datetime import datetime

COLUMNS = [
    ('mail_queue_item', 'deferred_until', 'DATETIME'),
    ('contact_send', 'size_bytes', 'INTEGER'),
]


def _has_column(conn, table, column):
    return column in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]

    conn = sqlite3.connect(path)
    try:
        todo = []
        print(f"Base : {path}")
        for table, column, sqltype in COLUMNS:
            need = not _has_column(conn, table, column)
            print(f"  colonne {table}.{column} : {'à ajouter' if need else 'présente'}")
            if need:
                todo.append((table, column, sqltype))

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return
        if not todo:
            print("Rien à faire (colonnes déjà présentes).")
            return

        backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        shutil.copy(path, backup)
        print(f"→ Sauvegarde : {backup}")

        for table, column, sqltype in todo:
            # NULL par défaut : aucune valeur à backfiller, aucun envoi existant touché.
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {sqltype}")
            print(f"  ✓ {table}.{column}")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_mail_queue_item_deferred_until "
                     "ON mail_queue_item (deferred_until)")
        conn.commit()
        print("✓ Migration appliquée.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
