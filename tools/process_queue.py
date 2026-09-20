#!/usr/bin/env python3
"""
Envoie une tranche de la file d'attente — commande destinée à un TIMER sur l'hôte.

Pensée pour être lancée en boucle sans surveillance (systemd timer, toutes les 5 min) :

    docker compose run --rm --no-deps app python tools/process_queue.py --quiet

Elle traite les campagnes ayant des mails en attente, les plus anciennes d'abord, en
respectant le débit et les plafonds (cf. `sending.py`), puis s'arrête. Ce qui reste part
au passage suivant. Rien à surveiller : sans mail en attente, elle ne fait rien et sort.

Garde-fous :
- **verrou partagé avec l'interface** : si un envoi est déjà en cours (timer précédent
  encore actif, ou bouton « Envoyer maintenant »), la commande sort sans rien faire ;
- **durée bornée** (`--max-seconds`, défaut 240) : la tranche finit avant le passage
  suivant du timer ;
- **campagnes en pause ignorées**.

Sorties : 0 = rien à faire ou tranche envoyée ; 1 = erreur (SMTP, base…) ;
2 = un autre envoi détenait le verrou (cas normal, à ne pas traiter comme une panne).

Usage :
    python tools/process_queue.py [--max-seconds 240] [--campaign <id>] [--quiet]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# Pas de fil d'envoi automatique ici : on importe l'application pour son contexte, et
# c'est cette commande qui envoie, une fois, sous le verrou.
os.environ['CONTACT_MAILER_NO_AUTOSEND'] = '1'

from app import app                      # noqa: E402  (après le sys.path)
import sending                           # noqa: E402


def main():
    args = sys.argv[1:]
    quiet = '--quiet' in args
    max_seconds = 240
    if '--max-seconds' in args:
        max_seconds = int(args[args.index('--max-seconds') + 1])
    only = args[args.index('--campaign') + 1] if '--campaign' in args else None

    def say(msg):
        if not quiet:
            print(msg)

    with app.app_context():
        try:
            with sending.send_lock() as lock_fd:
                campaigns = [only] if only else sending.pending_campaigns()
                if not campaigns:
                    say('Rien en attente.')
                    return 0

                quota = sending.quota_state()
                say(f"File : {len(campaigns)} campagne(s) ; marge {quota['left_hour']}/h, "
                    f"{quota['left_day']}/j, {quota['left_mb_hour']} Mo/h")

                import time
                deadline = time.monotonic() + max_seconds
                total_sent = total_errors = 0
                for campaign in campaigns:
                    left = deadline - time.monotonic()
                    if left <= 1:
                        say('Durée de la tranche atteinte : la suite au prochain passage.')
                        break
                    sending._write_holder(lock_fd, campaign)   # « qui envoie » pour l'interface
                    sent, errors, stopped, warnings = sending.run_campaign(campaign, max_seconds=left)
                    if sent is None:
                        # `errors` porte le message d'échec (SMTP absent, campagne sans
                        # modèle…) : on le signale et on sort en erreur.
                        print(f'{campaign} : {errors}', file=sys.stderr)
                        return 1
                    total_sent += sent
                    total_errors += errors
                    for w in warnings:
                        say(f'  {campaign} : {w}')
                    if sent or errors:
                        say(f'  {campaign} : {sent} envoyés, {errors} erreurs'
                            + (f' — arrêt : {stopped}' if stopped else ''))
                    if stopped is not None and stopped.halt:
                        when = sending.humanize_delay(stopped.resume_at)
                        say(f'Arrêt de la tranche ({stopped})'
                            + (f' — reprise {when}.' if when else '.'))
                        break

                say(f'Tranche terminée : {total_sent} envoyés, {total_errors} erreurs.')
                return 0
        except sending.SendBusy as e:
            say(str(e))
            return 2
        except Exception as e:
            print(f'Erreur : {e}', file=sys.stderr)
            return 1


if __name__ == '__main__':
    sys.exit(main())
