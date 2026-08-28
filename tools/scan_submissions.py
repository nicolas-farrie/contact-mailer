#!/usr/bin/env python3
"""Scan des demandes de diffusion + notification des modérateurs (idempotent).

À déclencher par un timer hôte (systemd timer / cron), typiquement toutes les N min :
    docker compose run --rm app python tools/scan_submissions.py

Anti-doublon par Message-ID (table notified_submission) → aucune double alerte, même
si le scan repasse ou coexiste avec le refresh à l'ouverture de la page. Best-effort :
ne lève pas (le module logge les erreurs).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app                     # noqa: E402
from config import Config               # noqa: E402
from submission_notifier import scan_and_notify   # noqa: E402


def main():
    with app.app_context():
        new, notified = scan_and_notify(Config)
    print(f"Demandes de diffusion — nouvelles : {new} · notifiées : {notified}")


if __name__ == '__main__':
    main()
