#!/usr/bin/env python3
"""Synchronise les listes alimentées par une source externe (NOÉ, …). Idempotent.

À déclencher par un timer hôte (systemd timer / cron), typiquement tous les quarts
d'heure pendant un événement :
    docker compose run --rm --no-deps app python tools/sync_lists.py

`run` et non `exec` : le script doit pouvoir tourner même si l'application ne démarre
pas. Et un ordonnanceur interne à l'app est exclu — gunicorn tourne avec deux workers,
il s'exécuterait deux fois.

N'écrit que dans `contact_liste` : aucun contact créé, aucun champ modifié, aucun
désabonnement révoqué (cf. list_sync.py). Un nouveau bénévole est compté, pas importé —
son entrée dans la base demande des décisions humaines (doublon probable, corbeille),
prises dans l'écran d'alimentation.

Usage :
    python tools/sync_lists.py                 # toutes les sources
    python tools/sync_lists.py --provider noe  # une seule
    python tools/sync_lists.py --quiet         # ne parle qu'en cas de changement
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app                    # noqa: E402
from list_sync import sync_all         # noqa: E402


def main():
    args = sys.argv[1:]
    quiet = '--quiet' in args
    provider = args[args.index('--provider') + 1] if '--provider' in args else None

    with app.app_context():
        results = sync_all(provider=provider)

    if not results:
        if not quiet:
            print('Aucune liste alimentée à synchroniser.')
        return 0

    total = {'added': 0, 'removed': 0, 'pending': 0}
    errors = []
    for r in results:
        for k in total:
            total[k] += r[k]
        if r['error']:
            errors.append(r)
        if not quiet or r['added'] or r['removed'] or r['error']:
            etat = f"✗ {r['error']}" if r['error'] else \
                   f"+{r['added']} −{r['removed']}" + (f" · {r['pending']} en attente" if r['pending'] else '')
            print(f"  {r['liste']} ← « {r['ref']} » : {etat}")

    if not quiet or total['added'] or total['removed'] or errors:
        print(f"{len(results)} liste(s) · {total['added']} ajout(s) · {total['removed']} retrait(s)"
              + (f" · {total['pending']} bénévole(s) en attente d'import" if total['pending'] else ''))

    # Sortie ≠ 0 si une source a échoué : le timer le remonte, et `systemctl status`
    # ou le journal le montre sans avoir à lire la sortie.
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
