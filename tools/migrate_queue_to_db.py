#!/usr/bin/env python3
"""
Migration one-shot : importe l'ancien data/mail_queue.json dans les tables
mail_campaign / mail_queue_item (la file d'envoi passe du fichier JSON à la DB).

- Idempotent-safe : refuse si les tables contiennent déjà des données (sauf --force).
- Les ids d'items ne sont PAS préservés (auto-incrément) : ils n'étaient pas
  référencés de façon persistante, et l'ancien schéma pouvait avoir des doublons.
- Après import réussi, l'ancien JSON est renommé en .migrated-<horodatage>
  (plus rien ne le lit) — c'est aussi la sauvegarde.

Usage :
    python tools/migrate_queue_to_db.py --dry-run     # aperçu, rien n'est écrit
    python tools/migrate_queue_to_db.py               # applique
    python tools/migrate_queue_to_db.py --file data/mail_queue.json
    python tools/migrate_queue_to_db.py --force       # importe même si tables non vides
"""
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db                       # noqa: E402
from models import MailCampaign, MailQueueItem  # noqa: E402


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    force = '--force' in args
    path = 'data/mail_queue.json'
    if '--file' in args:
        path = args[args.index('--file') + 1]

    if not os.path.exists(path):
        print(f"✗ Fichier introuvable : {path} (rien à migrer)")
        return

    with open(path, encoding='utf-8') as f:
        data = json.load(f)
    if isinstance(data, list):          # très ancien format (liste simple)
        data = {'queue': data, 'campaigns': {}}
    queue = data.get('queue', [])
    campaigns = data.get('campaigns', {})
    print(f"Source : {path}")
    print(f"  campagnes : {len(campaigns)}   items : {len(queue)}")

    with app.app_context():
        db.create_all()  # s'assure que mail_campaign / mail_queue_item existent

        existing = (db.session.query(MailQueueItem).count()
                    + db.session.query(MailCampaign).count())
        if existing and not force:
            print(f"✗ Les tables contiennent déjà {existing} enregistrement(s).")
            print("  Utilise --force pour importer quand même (risque de doublons).")
            return

        if dry_run:
            print("(--dry-run : aucune écriture)")
            return

        # Campagnes (templates)
        for cid, tpl in campaigns.items():
            camp = db.session.get(MailCampaign, cid) or MailCampaign(id=cid)
            camp.subject = tpl.get('subject', '')
            camp.body = tpl.get('body', '')
            camp.format = tpl.get('format', 'text')
            camp.sent_by = tpl.get('sent_by')
            camp.include_unsubscribe = bool(tpl.get('include_unsubscribe'))
            camp.attachments = tpl.get('attachments')
            camp.liste_id = tpl.get('liste_id')
            camp.submission_id = tpl.get('submission_id')
            camp.archived = bool(tpl.get('archived'))
            db.session.add(camp)

        # Items de la file (id auto-incrémenté, non préservé)
        for it in queue:
            db.session.add(MailQueueItem(
                campaign_id=it.get('campaign_id'),
                contact=it.get('contact'),
                status=it.get('status', 'pending'),
                attempts=it.get('attempts', 0) or 0,
                error=it.get('error'),
                sent_at=_parse_dt(it.get('sent_at')),
                created_at=_parse_dt(it.get('created_at')) or datetime.now(),
            ))

        db.session.commit()

        # Renomme l'ancien JSON (= sauvegarde, et plus rien ne le lit désormais)
        migrated = f"{path}.migrated-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        os.rename(path, migrated)
        print(f"✓ Import terminé : {len(campaigns)} campagne(s), {len(queue)} item(s).")
        print(f"→ Ancien fichier renommé : {migrated}")


if __name__ == '__main__':
    main()
