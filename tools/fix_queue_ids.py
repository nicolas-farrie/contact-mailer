#!/usr/bin/env python3
"""
Correctif one-shot : réattribue des ids UNIQUES aux items de la file d'envoi.

Contexte : l'ancien code générait `id = len(queue) + 1`, qui recycle des ids
après suppression de campagnes → collisions → mark_sent/mark_error frappent le
mauvais item, le vrai reste figé en `pending`. Le code est corrigé (max+1), mais
les fichiers de file déjà en prod gardent leurs doublons : ce script les répare.

Ne touche PAS aux statuts ni au contenu : il renumérote simplement les items
1..N dans l'ordre courant. Une sauvegarde est faite avant écriture.

Usage :
    python tools/fix_queue_ids.py                 # applique (avec backup)
    python tools/fix_queue_ids.py --dry-run       # montre sans écrire
    python tools/fix_queue_ids.py --file data/mail_queue.json
"""
import json
import shutil
import sys
from datetime import datetime


def main():
    args = sys.argv[1:]
    dry_run = '--dry-run' in args
    path = 'data/mail_queue.json'
    if '--file' in args:
        path = args[args.index('--file') + 1]

    with open(path, encoding='utf-8') as f:
        data = json.load(f)

    queue = data.get('queue', [])
    ids = [i.get('id') for i in queue]
    dupes = len(ids) - len(set(ids))
    print(f"Fichier   : {path}")
    print(f"Items     : {len(queue)}")
    print(f"Ids uniques : {len(set(ids))}  |  doublons : {dupes}")

    if dupes == 0:
        print("✓ Aucun doublon — rien à faire.")
        return

    # Réattribution 1..N dans l'ordre courant (préserve tout le reste).
    for new_id, item in enumerate(queue, start=1):
        item['id'] = new_id
    print(f"→ Renumérotation en 1..{len(queue)}")

    if dry_run:
        print("(--dry-run : aucune écriture)")
        return

    backup = f"{path}.bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    shutil.copy(path, backup)
    print(f"→ Sauvegarde : {backup}")

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print("✓ Fichier corrigé.")


if __name__ == '__main__':
    main()
