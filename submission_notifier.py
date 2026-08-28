"""Notification des demandes de diffusion aux modérateurs.

Scanne la boîte IMAP des demandes et, pour chaque NOUVELLE demande (Message-ID pas
encore notifié, cf. table NotifiedSubmission), envoie un email d'alerte à tous les
utilisateurs actifs disposant d'un email. Anti-doublon partagé avec le refresh à
l'ouverture de la page. Idempotent — déclenché par un timer hôte (tools/scan_submissions.py)
ou réutilisable ailleurs. Best-effort : logge et continue, ne lève pas vers l'appelant.
"""
import logging

import imap_submissions
from models import db, User, NotifiedSubmission
from helpers import get_setting


def notify_enabled():
    """Flag admin (Paramètres › Général). Défaut = activé."""
    return get_setting('submission_notify_enabled', '1') != '0'


def _recipients():
    return [u.email.strip() for u in User.query.filter_by(is_active=True).all()
            if u.email and u.email.strip()]


def _build_mailer(config):
    from mailer import Mailer
    return Mailer(config.SMTP_HOST, config.SMTP_PORT, config.SMTP_USER,
                  config.SMTP_PASSWORD, config.SMTP_SENDER_EMAIL,
                  config.SMTP_SENDER_NAME or '', config.SMTP_USE_TLS)


def _notification(config, sub):
    link = f"{config.BASE_URL.rstrip('/')}/mailing/submissions"
    subject = (sub.get('subject') or '(sans sujet)').strip()
    frm = sub.get('from_name') or sub.get('from_email') or 'expéditeur inconnu'
    n_pj = sub.get('attachment_count')
    pj_line = f"Pièces jointes : {n_pj}\n" if n_pj else ""
    body = (
        "Une nouvelle demande de diffusion vient d'arriver.\n\n"
        f"Expéditeur : {frm} <{sub.get('from_email', '')}>\n"
        f"Sujet : {subject}\n"
        f"{pj_line}\n"
        f"Traitez-la depuis l'application : {link}\n"
    )
    return f"[Demande de diffusion] {subject}", body


def scan_and_notify(config):
    """Notifie les demandes non encore notifiées. Retourne (nb_nouvelles, nb_notifiées).
    L'anti-doublon (NotifiedSubmission par Message-ID) protège les re-scans."""
    if not config.IMAP_HOST:
        return 0, 0
    try:
        subs = imap_submissions.fetch_submissions(config)
    except Exception as e:
        logging.error('scan demandes de diffusion : lecture IMAP échouée : %s', e)
        return 0, 0

    new = [s for s in subs if s.get('message_id')
           and db.session.get(NotifiedSubmission, s['message_id']) is None]
    if not new:
        return 0, 0
    if not notify_enabled():
        # Notifications désactivées : on ne notifie NI n'enregistre → réactivation
        # ultérieure alertera les demandes encore en attente.
        return len(new), 0

    recipients = _recipients()
    if not recipients or not config.SMTP_HOST:
        # Rien pour envoyer : on n'enregistre pas non plus (on réessaiera plus tard).
        logging.warning('scan demandes : %d nouvelle(s) mais aucun destinataire/SMTP → non notifié', len(new))
        return len(new), 0

    mailer = _build_mailer(config)
    notified = 0
    try:
        mailer.connect()
        for s in new:
            subj, body = _notification(config, s)
            for to in recipients:
                try:
                    mailer.send_single(to, subj, body, None)
                except Exception as e:
                    logging.error('notif demande → %s échouée : %s', to, e)
            db.session.add(NotifiedSubmission(message_id=s['message_id']))
            notified += 1
        db.session.commit()
    finally:
        try:
            mailer.quit()
        except Exception:
            pass
    return len(new), notified
