#!/usr/bin/env python3
"""Checkpoint WAL → base principale (PRAGMA wal_checkpoint(TRUNCATE)).

En mode WAL, les dernières transactions vivent dans `contacts.db-wal` tant qu'un
checkpoint ne les a pas recopiées dans `contacts.db`. `docker compose stop` ne
checkpointe PAS forcément (retour d'expérience 2026-08-29) → un `cp contacts.db`
SEUL peut rater des données. Lancer ce script AVANT une copie manuelle de
`contacts.db` isolée du -wal.

Plus sûr pour une manip hôte ponctuelle : tar de TOUT le dossier `data/`
(contacts.db + -wal + -shm ensemble). Et les backups applicatifs
(helpers.backup_database, API sqlite3.backup) sont DÉJÀ cohérents en WAL — ce
script ne leur est pas nécessaire.

Usage :
    docker compose exec -T app python tools/checkpoint.py
    python tools/checkpoint.py --db data/contacts.db
"""
import sqlite3
import sys


def main():
    args = sys.argv[1:]
    path = 'data/contacts.db'
    if '--db' in args:
        path = args[args.index('--db') + 1]
    conn = sqlite3.connect(path)
    try:
        row = conn.execute('PRAGMA wal_checkpoint(TRUNCATE)').fetchone()
        conn.commit()
        if row:
            print(f"checkpoint WAL : busy={row[0]} pages_log={row[1]} pages_checkpointées={row[2]}")
            if row[0]:
                print("⚠ busy=1 : des écritures étaient en cours — relancer, ou arrêter l'app d'abord.")
        else:
            print("checkpoint WAL effectué.")
    finally:
        conn.close()


if __name__ == '__main__':
    main()
