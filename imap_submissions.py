"""Lecture des demandes de diffusion reçues sur une boîte IMAP dédiée.

Workflow : un contact envoie un mail à une adresse dédiée (ex: demande-diffusion@...)
pour demander la diffusion d'un message à une liste. Un utilisateur de l'app consulte
ces demandes, les utilise comme brouillon pour un mailing, puis le message est déplacé
vers un dossier "Traité" (état géré par les dossiers IMAP, pas de table en DB).
"""
import base64
import imaplib
import email
from email.header import decode_header
from email.utils import parseaddr


def _decode(value):
    if not value:
        return ''
    parts = decode_header(value)
    decoded = ''
    for part, charset in parts:
        if isinstance(part, bytes):
            decoded += part.decode(charset or 'utf-8', errors='replace')
        else:
            decoded += part
    return decoded


def _connect(config):
    conn = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
    conn.login(config.IMAP_USER, config.IMAP_PASSWORD)
    return conn


def _search_criteria(config):
    """Critère de recherche IMAP : tous les messages, ou ceux qui correspondent
    aux filtres IMAP_TO_FILTER (alias destinataire) et/ou IMAP_SUBJECT_FILTER
    (sujet) configurés."""
    criteria = []
    if config.IMAP_TO_FILTER:
        criteria += ['TO', f'"{config.IMAP_TO_FILTER}"']
    if config.IMAP_SUBJECT_FILTER:
        criteria += ['SUBJECT', f'"{config.IMAP_SUBJECT_FILTER}"']
    return criteria or ['ALL']


def _extract_body_and_attachments(msg):
    body_text = ''
    body_html = ''
    attachments = []
    inline_images = {}  # Content-ID (sans < >) -> (content_type, payload)

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = part.get_content_disposition()
            content_id = (part.get('Content-ID') or '').strip('<>')

            if disposition == 'attachment':
                filename = _decode(part.get_filename())
                payload = part.get_payload(decode=True)
                if filename and payload:
                    attachments.append({
                        'filename': filename,
                        'content_type': content_type,
                        'size': len(payload),
                        'payload': payload,
                    })
            elif content_type.startswith('image/') and content_id:
                payload = part.get_payload(decode=True)
                if payload:
                    inline_images[content_id] = (content_type, payload)
            elif content_type == 'text/plain' and not body_text:
                charset = part.get_content_charset() or 'utf-8'
                body_text = part.get_payload(decode=True).decode(charset, errors='replace')
            elif content_type == 'text/html' and not body_html:
                charset = part.get_content_charset() or 'utf-8'
                body_html = part.get_payload(decode=True).decode(charset, errors='replace')
    else:
        charset = msg.get_content_charset() or 'utf-8'
        payload = msg.get_payload(decode=True)
        content = payload.decode(charset, errors='replace') if payload else ''
        if msg.get_content_type() == 'text/html':
            body_html = content
        else:
            body_text = content

    # Remplacer les références cid: par des data URI pour affichage direct
    # dans l'éditeur et conservation dans le mail envoyé
    for cid, (content_type, payload) in inline_images.items():
        data_uri = f'data:{content_type};base64,{base64.b64encode(payload).decode("ascii")}'
        body_html = body_html.replace(f'cid:{cid}', data_uri)

    return body_text, body_html, attachments


def fetch_submissions(config):
    """Liste les demandes en attente dans le dossier IMAP configuré."""
    conn = _connect(config)
    try:
        conn.select(config.IMAP_FOLDER)
        status, data = conn.search(None, *_search_criteria(config))
        if status != 'OK':
            return []

        submissions = []
        for uid in data[0].split():
            status, msg_data = conn.fetch(uid, '(RFC822)')
            if status != 'OK':
                continue
            msg = email.message_from_bytes(msg_data[0][1])

            body_text, body_html, attachments = _extract_body_and_attachments(msg)
            name, addr = parseaddr(_decode(msg.get('From', '')))

            submissions.append({
                'uid': uid.decode(),
                'from_name': name,
                'from_email': addr,
                'subject': _decode(msg.get('Subject', '')),
                'date': msg.get('Date', ''),
                'body_text': body_text,
                'body_html': body_html,
                'attachments': [
                    {'filename': a['filename'], 'size': a['size']}
                    for a in attachments
                ],
            })

        # Plus récent en premier
        submissions.reverse()
        return submissions
    finally:
        conn.logout()


def get_submission(config, uid):
    """Récupère le détail complet (corps + pièces jointes avec contenu) d'une demande."""
    conn = _connect(config)
    try:
        conn.select(config.IMAP_FOLDER)
        status, msg_data = conn.fetch(uid.encode(), '(RFC822)')
        if status != 'OK' or not msg_data[0]:
            return None

        msg = email.message_from_bytes(msg_data[0][1])
        body_text, body_html, attachments = _extract_body_and_attachments(msg)
        name, addr = parseaddr(_decode(msg.get('From', '')))

        return {
            'uid': uid,
            'from_name': name,
            'from_email': addr,
            'subject': _decode(msg.get('Subject', '')),
            'date': msg.get('Date', ''),
            'body_text': body_text,
            'body_html': body_html,
            'attachments': attachments,
        }
    finally:
        conn.logout()


def mark_processed(config, uid):
    """Déplace le message vers le dossier 'Traité'."""
    conn = _connect(config)
    try:
        conn.select(config.IMAP_FOLDER)

        # Créer le dossier de destination s'il n'existe pas
        status, _ = conn.select(config.IMAP_PROCESSED_FOLDER)
        if status != 'OK':
            conn.create(config.IMAP_PROCESSED_FOLDER)
        conn.select(config.IMAP_FOLDER)

        uid_bytes = uid.encode()
        conn.copy(uid_bytes, config.IMAP_PROCESSED_FOLDER)
        conn.store(uid_bytes, '+FLAGS', '\\Deleted')
        conn.expunge()
    finally:
        conn.logout()


def count_pending(config):
    """Nombre de demandes en attente (pour le badge de navigation)."""
    conn = _connect(config)
    try:
        conn.select(config.IMAP_FOLDER)
        status, data = conn.search(None, *_search_criteria(config))
        if status != 'OK':
            return 0
        return len(data[0].split())
    finally:
        conn.logout()
