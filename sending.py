"""Boucle d'envoi de la file d'attente, partagée par l'interface et la commande.

Extrait de `blueprints/mailing.py` pour que `tools/process_queue.py` (lancé par un timer
sur l'hôte) et le bouton « Envoyer maintenant » exécutent EXACTEMENT le même code : un
seul comportement à comprendre, un seul à corriger.

Trois garde-fous, tous nécessaires sur un SMTP mutualisé :
- **le verrou** (`send_lock`) : deux envois simultanés doubleraient le débit réel vu par
  l'hébergeur, et deux processus pourraient prendre le même mail en file ;
- **les plafonds glissants**, calculés sur le journal `contact_send` écrit au fil des
  envois (fenêtres 1 h / 24 h, tous envois confondus) ;
- **la durée bornée** : sous gunicorn la requête est coupée à 300 s, et pour le timer une
  tranche doit finir avant le passage suivant.

Ce qui reste EN FILE après un arrêt est repris au passage suivant, sans doublon : chaque
mail est marqué envoyé un par un.
"""
import errno
import fcntl
import logging
import os
import threading
import time
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

from config import Config
from models import db, ContactSend, MailCampaign, MailQueueItem, utcnow

LOCK_PATH = 'data/.send.lock'
log = logging.getLogger(__name__)


class SendBusy(RuntimeError):
    """Un autre envoi détient le verrou."""


@contextmanager
def send_lock(path=LOCK_PATH):
    """Verrou exclusif inter-processus (interface ET commande) ; libéré même en cas de
    plantage, puisque le noyau relâche le verrou à la fermeture du descripteur."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fd = open(path, 'w')
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            if e.errno in (errno.EACCES, errno.EAGAIN):
                raise SendBusy('Un envoi est déjà en cours.')
            raise
        try:
            fd.write(f'{os.getpid()}\n')
            fd.flush()
        except Exception:
            pass
        yield
    finally:
        fd.close()


def _sent_since(delta, now=None):
    now = now or utcnow()
    return db.session.query(db.func.count(ContactSend.id)).filter(
        ContactSend.sent_at >= now - delta).scalar() or 0


def quota_state():
    """Ce qu'il reste à envoyer dans l'heure et dans la journée (None = illimité).

    Sert au garde-fou de la boucle et à l'affichage de la file : savoir qu'il reste
    12 mails autorisés cette heure-ci explique un envoi qui s'arrête.
    """
    now = utcnow()
    max_hour, max_day = Config.MAIL_MAX_PER_HOUR, Config.MAIL_MAX_PER_DAY
    used_hour, used_day = _sent_since(timedelta(hours=1), now), _sent_since(timedelta(days=1), now)
    return {
        'used_hour': used_hour, 'max_hour': max_hour,
        'used_day': used_day, 'max_day': max_day,
        'left_hour': max(0, max_hour - used_hour) if max_hour else None,
        'left_day': max(0, max_day - used_day) if max_day else None,
    }


def pending_campaigns(include_paused=False):
    """Identifiants des campagnes ayant des mails EN ATTENTE, plus anciennes d'abord."""
    rows = (db.session.query(MailQueueItem.campaign_id)
            .filter(MailQueueItem.status == 'pending')
            .group_by(MailQueueItem.campaign_id)
            .order_by(db.func.min(MailQueueItem.id)).all())
    ids = [r[0] for r in rows]
    if include_paused:
        return ids
    paused = {c.id for c in MailCampaign.query.filter_by(paused=True).all()}
    return [i for i in ids if i not in paused]


def run_campaign(campaign, max_seconds=None):
    """Envoie les mails en attente d'une campagne. Retourne (sent, errors, stopped, warnings).

    `stopped` porte la raison d'un arrêt anticipé (plafond, durée, pause), None sinon.
    En cas d'échec bloquant, retourne (None, message, None, []).
    Le verrou est pris par l'appelant (cf. `send_lock`).
    """
    from mailer import Mailer, EmailTemplate, MailQueue
    from helpers import get_setting

    warnings = []
    if not Config.SMTP_HOST:
        return (None, 'SMTP non configuré', None, warnings)

    camp = db.session.get(MailCampaign, campaign) if campaign else None
    if camp is not None and camp.paused:
        return (0, 0, 'campagne en pause', warnings)

    queue = MailQueue()
    pending = queue.get_pending(campaign)
    if not pending:
        return (0, 0, None, warnings)

    tpl = queue.get_campaign_template(campaign)
    if not tpl:
        return (None, 'Template de campagne introuvable', None, warnings)

    mailer = Mailer(
        smtp_host=Config.SMTP_HOST,
        smtp_port=Config.SMTP_PORT,
        smtp_user=Config.SMTP_USER,
        smtp_password=Config.SMTP_PASSWORD,
        sender_email=Config.SMTP_SENDER_EMAIL,
        sender_name=Config.SMTP_SENDER_NAME,
        use_tls=Config.SMTP_USE_TLS
    )

    mail_format = tpl.get('format', 'text')
    include_unsubscribe = tpl.get('include_unsubscribe', False)
    attachments = tpl.get('attachments', [])
    reply_to = tpl.get('reply_to')

    if mail_format == 'html':
        template = EmailTemplate(subject=tpl['subject'], body_text='', body_html=tpl['body'])
    else:
        template = EmailTemplate(subject=tpl['subject'], body_text=tpl['body'])

    delay = 60.0 / Config.MAIL_RATE_PER_MINUTE
    sent = 0
    errors = 0

    # Toggle « Gestion du bounce » (Paramètres) : OFF → pas de Return-Path bounce forcé
    # en enveloppe (évite le rejet SMTP 553 sur les serveurs stricts).
    bounce_on = get_setting('bounce_enabled', '1') != '0'
    bounce_return_path = (Config.BOUNCE_RETURN_PATH or Config.BOUNCE_IMAP_USER or None) if bounce_on else None

    quota = quota_state()
    prior_hour, prior_day = quota['used_hour'], quota['used_day']
    max_hour, max_day = quota['max_hour'], quota['max_day']
    stopped = None
    if max_seconds is None:
        max_seconds = Config.MAIL_MAX_RUN_SECONDS
    deadline = time.monotonic() + max_seconds if max_seconds else None

    # UNE seule connexion SMTP pour toute la campagne (au lieu d'une par email).
    try:
        mailer.connect()
    except Exception as e:
        return (None, f'Connexion SMTP impossible : {e}', None, warnings)

    for item in pending:
        # Garde-fous anti-blocage : on s'arrête AVANT de dépasser les plafonds ;
        # les items non traités restent EN ATTENTE (repris au passage suivant).
        if max_hour and (prior_hour + sent) >= max_hour:
            stopped = f'plafond horaire atteint ({max_hour}/h)'
            break
        if max_day and (prior_day + sent) >= max_day:
            stopped = f'plafond journalier atteint ({max_day}/j)'
            break
        # Durée bornée : mieux vaut s'arrêter nous-mêmes que d'être coupés par gunicorn
        # en pleine boucle, ou de déborder sur le passage suivant du timer.
        if deadline and time.monotonic() >= deadline:
            stopped = 'durée maximale de la tranche atteinte'
            break
        contact = item['contact']

        # Construire l'URL de désabonnement par contact
        unsub_url = None
        if include_unsubscribe and contact.get('uid'):
            unsub_url = f"{Config.BASE_URL}/unsubscribe/{contact['uid']}"

        try:
            subj, body_text, body_html = template.render(contact, unsubscribe_url=unsub_url)
            mailer.send_single(contact['email'], subj, body_text, body_html,
                               unsubscribe_url=unsub_url, attachments=attachments,
                               return_path=bounce_return_path, reply_to=reply_to)
            queue.mark_sent(item['id'])
            sent += 1
            # Journal écrit AU FIL DES ENVOIS : il sert au calcul des plafonds, et une
            # écriture groupée en fin de boucle disparaissait si l'envoi était
            # interrompu — la reprise sous-comptait alors les mails déjà partis et
            # pouvait dépasser la limite de l'hébergeur (incident L-SPAM00 du 13/08).
            if contact.get('id'):
                try:
                    db.session.add(ContactSend(contact_id=contact['id'],
                                               campaign_id=campaign, sent_at=utcnow()))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception as e:
            queue.mark_error(item['id'], str(e))
            errors += 1
        time.sleep(delay)

    # Copie récapitulative à l'expéditeur, seulement quand la campagne est TERMINÉE :
    # avec un envoi étalé en tranches, une copie par passage inonderait la boîte.
    remaining = queue.get_pending(campaign)
    if not remaining:
        try:
            _send_recap(mailer, template, tpl, campaign, pending, sent, errors, attachments)
        except Exception as e:
            warnings.append(f'Copie expéditeur non envoyée : {e}')

    mailer.quit()   # ferme la connexion SMTP persistante de la campagne
    return (sent, errors, stopped, warnings)


def run_pending(max_seconds):
    """Envoie une tranche : chaque campagne en attente, jusqu'au plafond ou à la durée.

    Retourne (sent, errors). Le verrou est pris par l'appelant.
    """
    deadline = time.monotonic() + max_seconds
    total_sent = total_errors = 0
    for campaign in pending_campaigns():
        left = deadline - time.monotonic()
        if left <= 1:
            break
        sent, errors, stopped, warnings = run_campaign(campaign, max_seconds=left)
        if sent is None:
            log.warning('Envoi automatique — %s : %s', campaign, errors)
            break
        total_sent += sent
        total_errors += errors
        for w in warnings:
            log.warning('Envoi automatique — %s : %s', campaign, w)
        if sent or errors:
            log.info('Envoi automatique — %s : %s envoyés, %s erreurs%s',
                     campaign, sent, errors, f' ({stopped})' if stopped else '')
        if stopped and 'plafond' in stopped:
            break       # plafond global : inutile d'essayer les campagnes suivantes
    return total_sent, total_errors


def _autosend_loop(app, interval):
    """Réveille la file à intervalle régulier, à l'intérieur du conteneur.

    Pas de planificateur externe : le verrou suffit à garantir un seul envoi à la fois,
    y compris avec plusieurs workers gunicorn ou un envoi lancé depuis l'interface. Une
    tranche ne dépasse jamais l'intervalle, pour ne pas mordre sur le réveil suivant.
    """
    time.sleep(min(interval, 30))     # laisser l'application démarrer (migrations…)
    max_seconds = max(30, min(Config.MAIL_MAX_RUN_SECONDS, interval - 30))
    while True:
        try:
            with app.app_context():
                if Config.SMTP_HOST:
                    with send_lock():
                        run_pending(max_seconds)
        except SendBusy:
            pass          # un envoi manuel est en cours : on repassera
        except Exception:
            log.exception('Envoi automatique : passage en échec')
        time.sleep(interval)


def start_autosend(app):
    """Démarre le fil d'envoi automatique, sauf si désactivé.

    Désactivé par `MAIL_AUTOSEND_INTERVAL=0`, et dans les commandes du dossier `tools/`
    (`CONTACT_MAILER_NO_AUTOSEND=1`) : elles importent l'application pour son contexte,
    pas pour envoyer en fond.
    """
    interval = Config.MAIL_AUTOSEND_INTERVAL
    if not interval or os.environ.get('CONTACT_MAILER_NO_AUTOSEND') == '1':
        return None
    thread = threading.Thread(target=_autosend_loop, args=(app, interval),
                              name='autosend', daemon=True)
    thread.start()
    log.info('Envoi automatique actif (toutes les %s s)', interval)
    return thread


def _send_recap(mailer, template, tpl, campaign, pending, sent, errors, attachments):
    """Copie récapitulative à l'expéditeur : le mail tel qu'il est parti + le bilan."""
    first_contact = pending[0]['contact']
    subj, body_text, body_html = template.render(first_contact)
    copy_subject = f"[Campagne {campaign} — {sent} envoyés, {errors} erreurs] {subj}"
    failed = [i['contact']['email'] for i in pending if i['status'] == 'error']

    recap_text = (
        f"\n\n{'='*60}\n"
        f"RÉCAPITULATIF CAMPAGNE : {campaign}\n"
        f"{'='*60}\n"
        f"  Envoyés  : {sent}\n"
        f"  Erreurs  : {errors}\n"
        f"  Total    : {len(pending)}\n"
    )
    if failed:
        recap_text += "\nEmails en erreur :\n" + "\n".join(f"  - {e}" for e in failed) + "\n"
    if attachments:
        recap_text += f"\nPièces jointes : {', '.join(Path(p).name for p in attachments)}\n"
    recap_text += f"{'='*60}\n"

    recap_html = (
        '<hr><div style="font-family:monospace;font-size:13px;color:#555;background:#f5f5f5;padding:1rem;border-radius:4px;">'
        f'<strong>Récapitulatif — {campaign}</strong><br><br>'
        f'Envoyés : <strong>{sent}</strong> &nbsp;|&nbsp; '
        f'Erreurs : <strong style="color:{"#c00" if errors else "#090"}">{errors}</strong> &nbsp;|&nbsp; '
        f'Total : <strong>{len(pending)}</strong>'
    )
    if failed:
        recap_html += '<br><br>Emails en erreur :<br>' + '<br>'.join(f'&nbsp;• {e}' for e in failed)
    if attachments:
        recap_html += f'<br><br>Pièces jointes : {", ".join(Path(p).name for p in attachments)}'
    recap_html += '</div>'

    mailer.send_single(Config.SMTP_SENDER_EMAIL, copy_subject,
                       body_text + recap_text,
                       (body_html + recap_html) if body_html else None,
                       attachments=attachments)
