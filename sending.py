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
import json
import logging
import os
import smtplib
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path

from config import Config
from models import db, ContactSend, MailCampaign, MailQueueItem, utcnow

LOCK_PATH = 'data/.send.lock'
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)
MB = 1024 * 1024

# Attente après un refus temporaire qui ne vient PAS d'un plafond (greylisting, boîte
# du destinataire pleine, serveur indisponible) : on espace, puis on renonce. Sans ce
# renoncement, un destinataire définitivement fâché resterait en file pour toujours.
DEFER_BACKOFF = [timedelta(minutes=5), timedelta(minutes=15), HOUR, timedelta(hours=4)]
MAX_ATTEMPTS = len(DEFER_BACKOFF) + 1

log = logging.getLogger(__name__)


class SendBusy(RuntimeError):
    """Un autre envoi détient le verrou."""


class Stop:
    """Raison d'un arrêt anticipé de la tranche, et quand ça repart.

    Porté jusqu'à l'interface : « interrompu, reprenez plus tard » n'aide personne si
    on ne dit pas si « plus tard » veut dire dix minutes ou demain matin.
    `halt` marque un arrêt qui vaut pour TOUTES les campagnes (plafond, refus global du
    serveur), par opposition à un arrêt propre à celle qu'on traite (pause, durée).
    """

    def __init__(self, reason, resume_at=None, halt=False):
        self.reason = reason
        self.resume_at = resume_at
        self.halt = halt

    def __str__(self):
        return self.reason


@contextmanager
def send_lock(path=LOCK_PATH, campaign=None):
    """Verrou exclusif inter-processus (interface ET commande) ; libéré même en cas de
    plantage, puisque le noyau relâche le verrou à la fermeture du descripteur.

    Le détenteur écrit qui il est : l'interface peut ainsi dire « envoi en cours » quand
    il l'est VRAIMENT, au lieu de le déduire d'un compteur (le bandeau annonçait un envoi
    en cours dès qu'une campagne était entamée, même à l'arrêt complet).
    """
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    # 'a+' et pas 'w' : ouvrir en écriture tronquerait AVANT même d'avoir le verrou,
    # effaçant l'identité du détenteur légitime.
    fd = open(path, 'a+')
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as e:
            if e.errno in (errno.EACCES, errno.EAGAIN):
                raise SendBusy('Un envoi est déjà en cours.')
            raise
        _write_holder(fd, campaign)
        yield fd
    finally:
        fd.close()


def _write_holder(fd, campaign):
    """Inscrit le détenteur du verrou (pid + campagne en cours) dans le fichier."""
    try:
        fd.seek(0)
        fd.truncate()
        fd.write(json.dumps({'pid': os.getpid(), 'campaign': campaign,
                             'since': utcnow().isoformat()}) + '\n')
        fd.flush()
    except Exception:
        pass          # l'information d'affichage ne doit jamais faire échouer un envoi


def current_send(path=LOCK_PATH):
    """Envoi réellement en cours : {'pid', 'campaign', 'since'}, ou None si rien ne tourne.

    Lecture sans blocage : on tente de prendre le verrou ; s'il se prend, personne
    n'envoie. Le verrou est relâché aussitôt (fermeture du descripteur).
    """
    try:
        fd = open(path, 'a+')
    except OSError:
        return None
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return None                   # libre : aucun envoi en cours
        except OSError:
            pass
        fd.seek(0)
        raw = fd.read().strip()
        try:
            return json.loads(raw) if raw else {'pid': None, 'campaign': None, 'since': None}
        except ValueError:
            return {'pid': None, 'campaign': None, 'since': None}
    finally:
        fd.close()


def _window(delta, now=None):
    """Envois de la fenêtre glissante, du plus ancien au plus récent : [(date, octets)]."""
    now = now or utcnow()
    rows = (db.session.query(ContactSend.sent_at, ContactSend.size_bytes)
            .filter(ContactSend.sent_at >= now - delta)
            .order_by(ContactSend.sent_at).all())
    return [(r[0], r[1] or 0) for r in rows]


def _sent_since(delta, now=None):
    now = now or utcnow()
    return db.session.query(db.func.count(ContactSend.id)).filter(
        ContactSend.sent_at >= now - delta).scalar() or 0


def _bytes_since(delta, now=None):
    now = now or utcnow()
    return db.session.query(db.func.coalesce(db.func.sum(ContactSend.size_bytes), 0)).filter(
        ContactSend.sent_at >= now - delta).scalar() or 0


def _release_at(delta, need, by_bytes=False, now=None):
    """Quand la fenêtre aura libéré `need` unités (mails, ou octets).

    La fenêtre est glissante : la place se libère au fur et à mesure que les envois
    d'il y a une heure en sortent. On cumule donc les plus anciens jusqu'à atteindre
    ce qu'il faut, et la reprise est datée de leur sortie.
    """
    if need <= 0:
        return None
    freed = 0
    for sent_at, size in _window(delta, now):
        freed += size if by_bytes else 1
        if freed >= need:
            return sent_at + delta
    return None       # la fenêtre entière n'y suffit pas : rien à promettre


def quota_state():
    """Marges restantes dans l'heure et dans la journée, en nombre ET en volume.

    `None` = illimité. Deux plafonds cohabitent chez l'hébergeur : le nombre de mails et
    le VOLUME cumulé (1000 Mo/h chez LWS). Avec des pièces jointes, c'est le second qui
    tombe en premier — le premier n'explique alors rien du tout.
    """
    now = utcnow()
    max_hour, max_day = Config.MAIL_MAX_PER_HOUR, Config.MAIL_MAX_PER_DAY
    max_bytes_hour = Config.MAIL_MAX_MB_PER_HOUR * MB
    max_bytes_day = Config.MAIL_MAX_MB_PER_DAY * MB
    used_hour, used_day = _sent_since(HOUR, now), _sent_since(DAY, now)
    used_bytes_hour, used_bytes_day = _bytes_since(HOUR, now), _bytes_since(DAY, now)
    return {
        'used_hour': used_hour, 'max_hour': max_hour,
        'used_day': used_day, 'max_day': max_day,
        'left_hour': max(0, max_hour - used_hour) if max_hour else None,
        'left_day': max(0, max_day - used_day) if max_day else None,
        'used_mb_hour': round(used_bytes_hour / MB, 1),
        'used_mb_day': round(used_bytes_day / MB, 1),
        'max_mb_hour': Config.MAIL_MAX_MB_PER_HOUR, 'max_mb_day': Config.MAIL_MAX_MB_PER_DAY,
        'left_bytes_hour': max(0, max_bytes_hour - used_bytes_hour) if max_bytes_hour else None,
        'left_bytes_day': max(0, max_bytes_day - used_bytes_day) if max_bytes_day else None,
        'left_mb_hour': round(max(0, max_bytes_hour - used_bytes_hour) / MB, 1) if max_bytes_hour else None,
        'left_mb_day': round(max(0, max_bytes_day - used_bytes_day) / MB, 1) if max_bytes_day else None,
    }


def classify_smtp_error(exc):
    """Lit un échec d'envoi : (temporaire ?, concerne tout l'envoi ?, texte lisible).

    Distinction capitale pour un envoi qui tourne sans personne devant l'écran : un 4xx
    veut dire « réessayez plus tard » (plafond atteint, greylisting, serveur occupé) et
    ne demande AUCUNE intervention, alors qu'un 5xx est un refus définitif qu'il faut
    montrer. Tout confondre, c'était transformer une limite horaire en 74 erreurs
    figées qu'un humain seul pouvait relancer (incident du 18/09/2026).
    Un refus de DESTINATAIRE ne concerne que lui ; un refus d'expéditeur ou de données
    vaut pour tous les mails qui suivent.
    """
    code, whole = None, True
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        whole = False
        codes = [c for c, _ in exc.recipients.values()]
        code = codes[0] if codes else None
    elif isinstance(exc, smtplib.SMTPResponseException):     # data, sender, auth, …
        code = exc.smtp_code
    elif isinstance(exc, (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError,
                          ConnectionError, TimeoutError, OSError)):
        return True, True, f'Serveur injoignable : {exc}'    # rien ne dit que c'est perdu
    text = str(exc)
    if code is not None:
        return 400 <= code < 500, whole, text
    return False, whole, text


def _defer_delay(attempts):
    """Attente avant un nouvel essai, d'après le nombre d'essais déjà faits."""
    return DEFER_BACKOFF[min(attempts, len(DEFER_BACKOFF) - 1)]


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
    # Marges de VOLUME, décomptées au fil de la tranche comme les compteurs de mails.
    left_bytes_hour, left_bytes_day = quota['left_bytes_hour'], quota['left_bytes_day']
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
            stopped = Stop(f'plafond horaire atteint ({max_hour}/h)',
                           _release_at(HOUR, 1), halt=True)
            break
        if max_day and (prior_day + sent) >= max_day:
            stopped = Stop(f'plafond journalier atteint ({max_day}/j)',
                           _release_at(DAY, 1), halt=True)
            break
        # Durée bornée : mieux vaut s'arrêter nous-mêmes que d'être coupés par gunicorn
        # en pleine boucle, ou de déborder sur le passage suivant du timer.
        if deadline and time.monotonic() >= deadline:
            stopped = Stop('durée maximale de la tranche atteinte', _next_autosend())
            break
        contact = item['contact']

        # Construire l'URL de désabonnement par contact
        unsub_url = None
        if include_unsubscribe and contact.get('uid'):
            unsub_url = f"{Config.BASE_URL}/unsubscribe/{contact['uid']}"

        try:
            subj, body_text, body_html = template.render(contact, unsubscribe_url=unsub_url)
            # Message assemblé AVANT d'être envoyé : sa taille réelle (pièces jointes
            # encodées comprises) décide s'il tient dans la marge de volume. C'est cette
            # limite-là, et non le nombre de mails, qui a arrêté la campagne du 18/09.
            envelope_from, raw = mailer.build_message(
                contact['email'], subj, body_text, body_html, unsubscribe_url=unsub_url,
                attachments=attachments, return_path=bounce_return_path, reply_to=reply_to)
            size = len(raw.encode('utf-8', 'replace'))

            too_big = _volume_stop(size, left_bytes_hour, left_bytes_day)
            if too_big is not None:
                if too_big == 'jamais':
                    # Un seul message plus gros que le plafond : le différer serait le
                    # rendre éternel. On le sort de la file, cause à l'appui.
                    queue.mark_error(item['id'],
                                     f'Message de {size // MB} Mo : au-dessus du plafond '
                                     f'de volume ({Config.MAIL_MAX_MB_PER_HOUR} Mo/h)')
                    errors += 1
                    continue
                stopped = too_big
                break

            mailer.deliver_raw(envelope_from, contact['email'], raw)
            queue.mark_sent(item['id'])
            sent += 1
            if left_bytes_hour is not None:
                left_bytes_hour -= size
            if left_bytes_day is not None:
                left_bytes_day -= size
            # Journal écrit AU FIL DES ENVOIS : il sert au calcul des plafonds, et une
            # écriture groupée en fin de boucle disparaissait si l'envoi était
            # interrompu — la reprise sous-comptait alors les mails déjà partis et
            # pouvait dépasser la limite de l'hébergeur (incident L-SPAM00 du 13/08).
            if contact.get('id'):
                try:
                    db.session.add(ContactSend(contact_id=contact['id'], campaign_id=campaign,
                                               sent_at=utcnow(), size_bytes=size))
                    db.session.commit()
                except Exception:
                    db.session.rollback()
        except Exception as e:
            temporary, whole, text = classify_smtp_error(e)
            attempts = item.get('attempts') or 0
            if temporary and attempts + 1 < MAX_ATTEMPTS:
                until = utcnow() + _defer_delay(attempts)
                if whole:
                    # Refus qui vaut pour l'expéditeur : toute la campagne attend, et la
                    # tranche s'arrête là plutôt que d'essuyer le même refus 100 fois.
                    queue.defer_campaign(campaign, until, text)
                    stopped = Stop(f'refus temporaire du serveur : {text}', until, halt=True)
                    break
                queue.mark_deferred(item['id'], until, text)
            else:
                queue.mark_error(item['id'], text)
                errors += 1
        time.sleep(delay)

    # Copie récapitulative à l'expéditeur, seulement quand la campagne est TERMINÉE :
    # avec un envoi étalé en tranches, une copie par passage inonderait la boîte. Les
    # mails différés comptent comme restants — sinon le récapitulatif partirait au
    # premier report, la campagne encore en cours.
    remaining = queue.get_pending(campaign, include_deferred=True)
    if not remaining:
        try:
            _send_recap(mailer, template, tpl, campaign, pending, sent, errors, attachments)
        except Exception as e:
            warnings.append(f'Copie expéditeur non envoyée : {e}')
        try:
            _alert_on_errors(mailer, queue, campaign, tpl)
        except Exception as e:
            warnings.append(f'Alerte non envoyée : {e}')

    mailer.quit()   # ferme la connexion SMTP persistante de la campagne
    return (sent, errors, stopped, warnings)


def _volume_stop(size, left_hour, left_day):
    """Le message tient-il dans la marge de volume ? None si oui, sinon un `Stop`
    (ou la chaîne 'jamais' pour un message plus gros que le plafond lui-même)."""
    max_hour_bytes = Config.MAIL_MAX_MB_PER_HOUR * MB
    max_day_bytes = Config.MAIL_MAX_MB_PER_DAY * MB
    if max_hour_bytes and size > max_hour_bytes:
        return 'jamais'
    if max_day_bytes and size > max_day_bytes:
        return 'jamais'
    if left_hour is not None and size > left_hour:
        return Stop(f'plafond de volume horaire atteint ({Config.MAIL_MAX_MB_PER_HOUR} Mo/h)',
                    _release_at(HOUR, size - left_hour, by_bytes=True), halt=True)
    if left_day is not None and size > left_day:
        return Stop(f'plafond de volume journalier atteint ({Config.MAIL_MAX_MB_PER_DAY} Mo/j)',
                    _release_at(DAY, size - left_day, by_bytes=True), halt=True)
    return None


def humanize_delay(when, now=None):
    """« dans 12 minutes », « dans 1 h 20 », « demain » — ou None si pas de date.

    Un DÉLAI, pas une heure : les dates sont stockées en UTC et l'heure affichée telle
    quelle induirait en erreur de deux heures l'été. Et c'est la vraie question de
    celui qui lit : dix minutes ou demain matin ?
    """
    if not when:
        return None
    if isinstance(when, str):     # les items de file voyagent en ISO (to_dict)
        try:
            when = datetime.fromisoformat(when)
        except ValueError:
            return None
    secs = (when - (now or utcnow())).total_seconds()
    if secs <= 60:
        return "dans moins d'une minute"
    minutes = round(secs / 60)     # arrondi, pas troncature : 11 min 59 s, c'est 12 minutes
    if minutes < 60:
        return f"dans {minutes} minutes"
    hours, rest = divmod(minutes, 60)
    if hours < 24:
        return f"dans {hours} h {rest:02d}" if rest else f"dans {hours} h"
    days = hours // 24
    return "demain" if days == 1 else f"dans {days} jours"


def _next_autosend():
    """Heure approximative du prochain réveil automatique de la file (None si éteint)."""
    interval = Config.MAIL_AUTOSEND_INTERVAL
    return utcnow() + timedelta(seconds=interval) if interval else None


def run_pending(max_seconds, lock_fd=None):
    """Envoie une tranche : chaque campagne en attente, jusqu'au plafond ou à la durée.

    Retourne (sent, errors). Le verrou est pris par l'appelant ; son descripteur, s'il
    est fourni, sert à publier la campagne en cours de traitement.
    """
    deadline = time.monotonic() + max_seconds
    total_sent = total_errors = 0
    for campaign in pending_campaigns():
        left = deadline - time.monotonic()
        if left <= 1:
            break
        if lock_fd is not None:
            _write_holder(lock_fd, campaign)
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
        if stopped is not None and stopped.halt:
            break       # plafond ou refus global : les campagnes suivantes n'iraient pas plus loin
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
                    with send_lock() as fd:
                        run_pending(max_seconds, lock_fd=fd)
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


def _alert_on_errors(mailer, queue, campaign, tpl):
    """Mail d'alerte quand une campagne se termine en laissant des erreurs définitives.

    Un envoi asynchrone se déroule sans personne devant l'écran : sans ce message, des
    destinataires non servis resteraient invisibles jusqu'à ce que quelqu'un pense à
    ouvrir la file. Coupable dans Paramètres, actif par défaut — l'oubli doit être le
    cas rare, pas la règle.
    """
    from helpers import get_setting

    if get_setting('alert_on_errors', '1') == '0':
        return
    stats = queue.get_stats(campaign)
    if not stats['error']:
        return

    items = [i for i in queue.queue if i['campaign_id'] == campaign and i['status'] == 'error']
    causes = {}
    for i in items:
        cause = (i.get('error') or i.get('last_error') or 'cause inconnue').strip()
        causes.setdefault(cause, []).append(i['contact'].get('email') or '—')

    name = tpl.get('name') or tpl.get('subject') or campaign
    lines = [f"La campagne « {name} » est terminée, mais {stats['error']} email(s) "
             f"n'ont pas pu être envoyés.", '',
             f"  Envoyés : {stats['sent']}",
             f"  Erreurs : {stats['error']}", '',
             "Causes :"]
    for cause, emails in causes.items():
        lines.append(f"\n  • {cause}")
        for e in emails[:20]:
            lines.append(f"      {e}")
        if len(emails) > 20:
            lines.append(f"      … et {len(emails) - 20} autre(s)")
    lines += ['', "Ces envois ne repartiront pas tout seuls : ouvrez la file d'attente de la",
              "campagne pour les relancer une fois la cause levée.",
              f"{Config.BASE_URL}/mailing/queue?campaign={campaign}"]

    mailer.send_single(Config.SMTP_SENDER_EMAIL,
                       f"[Alerte] {name} — {stats['error']} envoi(s) en erreur",
                       '\n'.join(lines))


def campaign_state(campaign_id, stats, paused=False, holder=None):
    """État affichable d'une campagne : (code, libellé, date de reprise).

    Un seul endroit décide de ce qui est vrai, pour que la file, l'historique et les
    messages disent la même chose. Le bandeau se fondait jusqu'ici sur le nombre de
    mails déjà traités : il annonçait « envoi en cours » sur une campagne à l'arrêt
    depuis des heures.
    """
    if holder and holder.get('campaign') == campaign_id:
        return ('sending', 'Envoi en cours', None)
    if paused:
        return ('paused', 'En pause', None)
    if stats.get('pending'):
        if stats.get('deferred') and stats['deferred'] >= stats['pending']:
            return ('waiting_quota', 'En attente de quota', stats.get('deferred_until'))
        return ('queued', 'En file', _next_autosend() if Config.MAIL_AUTOSEND_INTERVAL else None)
    if stats.get('error'):
        return ('done_errors', f"Terminé — {stats['error']} en erreur", None)
    if stats.get('sent'):
        return ('done', 'Terminé', None)
    return ('empty', 'Rien à envoyer', None)


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
