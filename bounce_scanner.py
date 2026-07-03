"""
Scanner de bounces SMTP : lit la boîte IMAP dédiée aux Return-Path,
parse les DSN (RFC 3464) et extrait les adresses email en erreur.

Stratégies de détection (du plus fiable au moins fiable) :
  1. Part MIME message/delivery-status → champ Final-Recipient
  2. Header X-Failed-Recipients (Gmail, certains serveurs)
  3. Regex sur le corps texte (fallback universel)
"""
import imaplib
import email
import re
from email.header import decode_header as _decode_header


_EMAIL_RE = re.compile(r'[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}')

# Mots-clés dans le sujet indiquant un bounce (insensible à la casse)
_BOUNCE_SUBJECTS = [
    'delivery status notification',
    'delivery failure',
    'mail delivery failed',
    'undelivered mail',
    'returned mail',
    'échec de remise',
    'non délivré',
    'mailer-daemon',
    'message non remis',
    'failure notice',
]


def _decode_str(value):
    if not value:
        return ''
    parts = _decode_header(value)
    result = ''
    for part, charset in parts:
        if isinstance(part, bytes):
            result += part.decode(charset or 'utf-8', errors='replace')
        else:
            result += part
    return result


def _is_bounce(msg):
    """Vérifie si le message est bien un bounce (DSN ou MAILER-DAEMON)."""
    subject = _decode_str(msg.get('Subject', '')).lower()
    from_addr = _decode_str(msg.get('From', '')).lower()
    content_type = msg.get_content_type() or ''

    if 'mailer-daemon' in from_addr:
        return True
    if any(kw in subject for kw in _BOUNCE_SUBJECTS):
        return True
    if 'multipart/report' in content_type:
        return True
    return False


def _extract_failed_address(msg):
    """Extrait l'adresse email en erreur depuis un message bounce.
    Retourne l'adresse en minuscules ou None si non trouvée."""

    # Stratégie 1 : header X-Failed-Recipients (Gmail, etc.)
    xfr = msg.get('X-Failed-Recipients', '')
    if xfr:
        m = _EMAIL_RE.search(xfr)
        if m:
            return m.group(0).lower()

    # Stratégie 2 : part MIME message/delivery-status (RFC 3464)
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'message/delivery-status':
                payload = part.get_payload()
                # payload peut être une liste de Message ou un string
                if isinstance(payload, list):
                    for sub in payload:
                        text = sub.as_string() if hasattr(sub, 'as_string') else str(sub)
                        addr = _parse_delivery_status(text)
                        if addr:
                            return addr
                elif isinstance(payload, str):
                    addr = _parse_delivery_status(payload)
                    if addr:
                        return addr

    # Stratégie 3 : regex sur le corps texte
    body = _get_text_body(msg)
    return _regex_fallback(body)


def _parse_delivery_status(text):
    """Parse un bloc delivery-status RFC 3464 et retourne Final-Recipient."""
    for line in text.splitlines():
        line_lower = line.lower()
        if 'final-recipient' in line_lower or 'original-recipient' in line_lower:
            m = _EMAIL_RE.search(line)
            if m:
                return m.group(0).lower()
    return None


def _get_text_body(msg):
    """Extrait le premier corps text/plain du message."""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == 'text/plain':
                charset = part.get_content_charset() or 'utf-8'
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(charset, errors='replace')
    else:
        if msg.get_content_type() == 'text/plain':
            charset = msg.get_content_charset() or 'utf-8'
            payload = msg.get_payload(decode=True)
            if payload:
                return payload.decode(charset, errors='replace')
    return ''


def _regex_fallback(text):
    """Cherche une adresse email near des mots-clés d'erreur dans le texte brut."""
    error_keywords = ['unknown', 'does not exist', 'no such user', 'user unknown',
                      'invalid', 'rejected', 'undeliverable', 'échec', 'introuvable',
                      'n\'existe pas', '550', '551', '552', '553', '554']
    lines = text.splitlines()
    for i, line in enumerate(lines):
        line_lower = line.lower()
        if any(kw in line_lower for kw in error_keywords):
            # Cherche un email dans cette ligne et les 2 lignes autour
            context = '\n'.join(lines[max(0, i-1):i+3])
            m = _EMAIL_RE.search(context)
            if m:
                return m.group(0).lower()
    return None


def scan_bounces(config):
    """Scanne la boîte IMAP bounce, retourne une liste de dicts :
    {'email': str, 'imap_uid': bytes, 'subject': str}
    """
    if not config.BOUNCE_IMAP_HOST:
        return []

    conn = imaplib.IMAP4_SSL(config.BOUNCE_IMAP_HOST, config.BOUNCE_IMAP_PORT)
    conn.login(config.BOUNCE_IMAP_USER, config.BOUNCE_IMAP_PASSWORD)

    results = []
    try:
        conn.select(config.BOUNCE_IMAP_FOLDER)
        status, data = conn.search(None, 'UNSEEN')
        if status != 'OK':
            return []

        for uid in data[0].split():
            status, msg_data = conn.fetch(uid, '(RFC822)')
            if status != 'OK' or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])

            if not _is_bounce(msg):
                continue

            failed_email = _extract_failed_address(msg)
            if failed_email:
                results.append({
                    'email': failed_email,
                    'imap_uid': uid,
                    'subject': _decode_str(msg.get('Subject', '')),
                })
    finally:
        conn.logout()

    return results


def mark_processed(config, imap_uid):
    """Déplace le message vers le dossier Traité."""
    conn = imaplib.IMAP4_SSL(config.BOUNCE_IMAP_HOST, config.BOUNCE_IMAP_PORT)
    conn.login(config.BOUNCE_IMAP_USER, config.BOUNCE_IMAP_PASSWORD)
    try:
        conn.select(config.BOUNCE_IMAP_FOLDER)
        status, _ = conn.select(config.BOUNCE_IMAP_PROCESSED_FOLDER)
        if status != 'OK':
            conn.create(config.BOUNCE_IMAP_PROCESSED_FOLDER)
        conn.select(config.BOUNCE_IMAP_FOLDER)
        conn.copy(imap_uid, config.BOUNCE_IMAP_PROCESSED_FOLDER)
        conn.store(imap_uid, '+FLAGS', '\\Deleted')
        conn.expunge()
    finally:
        conn.logout()
