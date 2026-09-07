#!/usr/bin/env python3
"""
Point d'entrée UNIQUE et STABLE des migrations DB (runner maison léger).

Appelé après le restart du conteneur, quelle que soit la version de départ.

⚠️ Utiliser `run`, PAS `exec` : quand le nouveau code attend une colonne que la
migration n'a pas encore créée, l'app meurt au démarrage (gunicorn --preload) et
part en boucle de redémarrage — `exec` exige un conteneur vivant, donc échoue avec
« is restarting, wait until the container is running », exactement quand on a besoin
de lui. `run` crée un conteneur neuf avec la même image et les mêmes volumes ; ce
script n'importe pas l'app (sqlite3 direct), il tourne donc sans elle.
Constaté en montant aubaygues de v2.2.1 à v2.3.0-beta.8 (colonne user.is_moderator).

    docker compose run --rm --no-deps app python tools/migrate.py            # applique le pending
    docker compose run --rm --no-deps app python tools/migrate.py --dry-run  # liste sans écrire
    docker compose run --rm --no-deps app python tools/migrate.py --stamp    # baseline (marque tout appliqué SANS exécuter)
    docker compose run --rm --no-deps app python tools/migrate.py --safe-only # n'applique que les migrations additives (pré-cutover)

Séquence complète d'une montée de version :
    1. sauvegarde   : tar czf backups/data-$(date +%Y%m%d-%H%M%S).tar.gz data
    2. nouveau tag  : éditer l'image dans docker-compose.yml, puis docker compose pull
    3. bascule      : docker compose up -d          (l'app peut boucler ici : normal)
    4. migrations   : docker compose run --rm --no-deps app python tools/migrate.py
    5. relance      : docker compose up -d          (l'app démarre pour de bon)

Principes :
- **Ledger** `schema_migrations(name, applied_at)` dans la base : source de vérité de
  ce qui a RÉELLEMENT tourné sur CETTE instance (indépendant de tout tag/.env qui peut
  mentir — cf. incident « latest = v1.2.10 »).
- **Ordre explicite** = l'ordre de cette liste (ordre d'ajout git ; `fix_queue_ids`
  AVANT `migrate_queue_to_db`, dépendance connue).
- **Idempotence** garantie par le ledger (on ne rejoue pas un script déjà enregistré) ;
  les scripts eux-mêmes restent idempotents (filet de sécurité).
- **Arrêt au premier échec** (exit ≠ 0 + nom du script fautif) → l'appelant sait que
  l'état n'est pas cohérent.
- **kind** : `safe` = ALTER/CREATE additif (applicable par avance) ; `cutover` = touche
  un fichier vivant (`data/mail_queue.json`), sûr seulement au cutover réel.
- Réutilise les scripts `tools/migrate_*.py` EXISTANTS sans les modifier (sous-process).
- Affiche `APP_VERSION` lue **dans le conteneur** (jamais dans `.env`/le tag).

⚠️ Ce runner N'EST PAS un remplaçant d'Alembic : le jour du passage à Postgres, on
migre toutes les instances à latest puis on bascule (Alembic prend le relais).
"""
import sqlite3
import subprocess
import sys
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB = 'data/contacts.db'

# Registre ORDONNÉ (ordre d'ajout git). NE PAS réordonner sans vérifier les dépendances.
MIGRATIONS = [
    ("migrate_add_uid", "safe"),
    ("migrate_add_users", "safe"),
    ("migrate_add_unsubscribe", "safe"),
    ("migrate_add_contact_user_link", "safe"),
    ("migrate_add_seafile_pwd", "safe"),
    ("migrate_add_genre_titre", "safe"),
    ("migrate_add_softdelete", "safe"),
    ("migrate_add_preferences", "safe"),
    ("migrate_add_bounces", "safe"),
    ("migrate_add_form_archive", "safe"),
    ("fix_queue_ids", "cutover"),          # doit précéder migrate_queue_to_db
    ("migrate_queue_to_db", "cutover"),    # renomme data/mail_queue.json
    ("migrate_add_custom_fields", "safe"),
    ("migrate_add_moderation_signature", "safe"),
    ("migrate_add_liste_ids", "safe"),
    ("migrate_add_liste_fields", "safe"),
    ("migrate_add_campaign_name", "safe"),
    ("migrate_add_form_blocks", "safe"),
    ("migrate_add_form_access_code", "safe"),
    ("migrate_add_form_is_test", "safe"),
    ("migrate_add_contact_send", "safe"),
    ("migrate_add_import_mapping", "safe"),
    ("migrate_add_queue_last_error", "safe"),
    ("migrate_add_contact_set_member", "safe"),
    ("migrate_add_campaign_use_selection", "safe"),
    ("migrate_add_contact_segment", "safe"),
    ("migrate_add_campaign_reply_to", "safe"),
    ("migrate_add_notified_submission", "safe"),
    ("migrate_add_user_is_moderator", "safe"),
    ("migrate_add_audit_log", "safe"),
]


def _db_path(argv):
    if '--db' in argv:
        return argv[argv.index('--db') + 1]
    return DEFAULT_DB


def _read_applied(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations "
                     "(name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
        conn.commit()
        return {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    finally:
        conn.close()


def _record(db_path, name):
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("INSERT OR IGNORE INTO schema_migrations (name, applied_at) VALUES (?, ?)",
                     (name, datetime.now(timezone.utc).isoformat()))
        conn.commit()
    finally:
        conn.close()


def main():
    argv = sys.argv[1:]
    dry_run = '--dry-run' in argv
    stamp = '--stamp' in argv
    safe_only = '--safe-only' in argv
    db_path = _db_path(argv)

    app_version = os.environ.get('APP_VERSION') or '(non définie — hors conteneur ?)'
    print(f"contact-mailer · migrations DB")
    print(f"  version (conteneur) : {app_version}")
    print(f"  base                : {db_path}")

    if not os.path.exists(db_path):
        print(f"✗ Base introuvable : {db_path}", file=sys.stderr)
        return 1

    applied = _read_applied(db_path)

    if stamp:
        n = 0
        for name, _kind in MIGRATIONS:
            if name not in applied:
                _record(db_path, name)
                n += 1
        print(f"✓ Baseline : {n} migration(s) marquée(s) appliquée(s) SANS exécution "
              f"({len(applied) + n} au total dans le ledger).")
        return 0

    pending = [(n, k) for (n, k) in MIGRATIONS if n not in applied]
    if safe_only:
        skipped = [n for (n, k) in pending if k == 'cutover']
        pending = [(n, k) for (n, k) in pending if k == 'safe']
        if skipped:
            print(f"  (--safe-only : {len(skipped)} migration(s) 'cutover' ignorée(s) : {', '.join(skipped)})")

    if not pending:
        print("✓ Base à jour — aucune migration en attente.")
        return 0

    print(f"\n{len(pending)} migration(s) en attente (dans l'ordre) :")
    for name, kind in pending:
        print(f"  - {name}  [{kind}]")

    if dry_run:
        print("\n(--dry-run : rien exécuté)")
        return 0

    for name, kind in pending:
        print(f"\n→ {name} [{kind}] …")
        cmd = [sys.executable, os.path.join(HERE, name + '.py')]
        if '--db' in argv:
            cmd += ['--db', db_path]
        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"\n✗ ÉCHEC sur « {name} » (code {res.returncode}). Chaîne INTERROMPUE — "
                  f"base potentiellement dans un état incomplet, à vérifier avant de continuer.",
                  file=sys.stderr)
            return res.returncode
        _record(db_path, name)
        print(f"✓ {name} — appliqué et enregistré au ledger.")

    print(f"\n✓ Terminé : {len(pending)} migration(s) appliquée(s).")
    return 0


if __name__ == '__main__':
    sys.exit(main())
