"""Lecture des demandes de diffusion reçues sur une boîte IMAP dédiée.

Workflow : un contact envoie un mail à une adresse dédiée (ex: demande-diffusion@...)
pour demander la diffusion d'un message à une liste. Un utilisateur de l'app consulte
ces demandes, les utilise comme brouillon pour un mailing, puis le message est déplacé
vers un dossier "Traité" (état géré par les dossiers IMAP, pas de table en DB).
"""
import base64
import imaplib
import email
import mimetypes
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime


def _fmt_date(raw):
    """Date d'email RFC 2822 → « JJ/MM/AAAA HH:MM » (repli sur la valeur brute)."""
    try:
        dt = parsedate_to_datetime(raw)
        return dt.strftime('%d/%m/%Y %H:%M') if dt else raw
    except Exception:
        return raw


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


def split_subject_lists(raw):
    """Sépare un sujet de demande de diffusion « liste1,liste2: vrai sujet ».

    - Retire un « mailing: » de tête s'il traîne (rétro-compat, insensible à la casse).
    - Découpe sur le PREMIER « : » : partie gauche = noms de listes (séparés par « , »),
      partie droite = le sujet réel (qui peut lui-même contenir des « : »).
    Renvoie (tokens_listes, sujet_après_2points, sujet_de_base_sans_mailing).
    Le matching des tokens vers de vraies listes (DB) est fait par l'appelant."""
    s = (raw or '').strip()
    if s[:8].lower() == 'mailing:':
        s = s[8:].strip()
    if ':' in s:
        left, right = s.split(':', 1)
        tokens = [t.strip() for t in left.split(',') if t.strip()]
        return tokens, right.strip(), s
    return [], s, s


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
        att_idx = 0
        for part in msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue  # conteneur (mixed/alternative/related), pas un contenu
            content_type = part.get_content_type()
            disposition = part.get_content_disposition()   # 'attachment' | 'inline' | None
            content_id = (part.get('Content-ID') or '').strip('<>')
            filename = _decode(part.get_filename())         # lit Content-Disposition filename ET Content-Type name

            # 1. Image inline référencée par un Content-ID → gardée inline (data URI),
            #    sauf si elle est explicitement une pièce jointe.
            if content_type.startswith('image/') and content_id and disposition != 'attachment':
                payload = part.get_payload(decode=True)
                if payload:
                    inline_images[content_id] = (content_type, payload)
            # 2. Pièce jointe : disposition=attachment OU simple présence d'un nom de
            #    fichier. On ne se fie PLUS à la seule disposition : beaucoup de clients
            #    l'omettent ou mettent « inline » sur de vraies PJ (Content-Type: …;
            #    name="x.pdf") → c'était la cause des pièces jointes perdues.
            elif disposition == 'attachment' or filename:
                payload = part.get_payload(decode=True)
                if payload:
                    att_idx += 1
                    if not filename:
                        ext = mimetypes.guess_extension(content_type) or ''
                        filename = f'piece-jointe-{att_idx}{ext}'
                    attachments.append({
                        'filename': filename,
                        'content_type': content_type,
                        'size': len(payload),
                        'payload': payload,
                    })
            # 3. Corps (première occurrence de chaque type)
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


def _extract_parens(b, start):
    """Extrait le groupe de parenthèses ÉQUILIBRÉ commençant au 1er '(' à/après `start`
    (en respectant les chaînes entre guillemets). Renvoie les octets ou b''."""
    i = b.find(b'(', start)
    if i < 0:
        return b''
    depth = 0
    j = i
    in_str = False
    while j < len(b):
        c = b[j:j+1]
        if in_str:
            if c == b'\\':
                j += 2
                continue
            if c == b'"':
                in_str = False
        elif c == b'"':
            in_str = True
        elif c == b'(':
            depth += 1
        elif c == b')':
            depth -= 1
            if depth == 0:
                return b[i:j+1]
        j += 1
    return b''


def _tokenize_bs(b):
    """Tokenise un BODYSTRUCTURE IMAP (octets) en listes Python imbriquées.
    Chaîne entre guillemets/atome (NIL, nombre) → str ; groupe (...) → list."""
    tokens = []
    stack = [tokens]
    i, n = 0, len(b)
    while i < n:
        c = b[i:i+1]
        if c == b'(':
            new = []
            stack[-1].append(new)
            stack.append(new)
            i += 1
        elif c == b')':
            if len(stack) > 1:
                stack.pop()
            i += 1
        elif c == b'"':
            j, buf = i + 1, b''
            while j < n:
                if b[j:j+1] == b'\\':
                    buf += b[j+1:j+2]; j += 2; continue
                if b[j:j+1] == b'"':
                    break
                buf += b[j:j+1]; j += 1
            stack[-1].append(buf.decode('utf-8', 'replace'))
            i = j + 1
        elif c == b' ':
            i += 1
        else:
            j = i
            while j < n and b[j:j+1] not in b' ()"':
                j += 1
            stack[-1].append(b[i:j].decode('utf-8', 'replace'))
            i = j
    return tokens


def _param_has(params, key):
    """params = liste plate [k1,v1,k2,v2,…] → vrai si `key` (insensible casse) présent."""
    if not isinstance(params, list):
        return False
    return any(isinstance(params[k], str) and params[k].lower() == key
               for k in range(0, len(params), 2))


def _find_disposition(node):
    """Cherche le body-fld-dsp d'une part feuille : sous-liste [\"attachment\"|\"inline\", (params)].
    Renvoie ('attachment'|'inline'|None, params_list)."""
    for el in node:
        if (isinstance(el, list) and el and isinstance(el[0], str)
                and el[0].lower() in ('attachment', 'inline')):
            dparams = el[1] if len(el) > 1 and isinstance(el[1], list) else []
            return el[0].lower(), dparams
    return None, []


def _count_attachments(node):
    """Compte récursivement les pièces jointes d'un arbre BODYSTRUCTURE tokenisé,
    en miroir de _extract_body_and_attachments : une PJ = disposition=attachment OU
    présence d'un nom de fichier ; on exclut les images inline référencées par CID."""
    if not isinstance(node, list) or not node:
        return 0
    if isinstance(node[0], list):        # multipart : enfants = listes en tête
        total = 0
        for child in node:
            if isinstance(child, list):
                total += _count_attachments(child)
            else:
                break                    # atteint le subtype (str) → fin des enfants
        return total
    # feuille : ["type","subtype",(params),id,desc,enc,size,...]
    if not isinstance(node[0], str):
        return 0
    mtype = node[0].lower()
    params = node[2] if len(node) > 2 and isinstance(node[2], list) else []
    content_id = node[3] if len(node) > 3 and isinstance(node[3], str) else 'NIL'
    disp, dparams = _find_disposition(node)
    has_name = _param_has(params, 'name') or _param_has(dparams, 'filename')
    if mtype == 'image' and content_id.upper() != 'NIL' and disp != 'attachment' and not has_name:
        return 0                         # image inline référencée par cid → pas une PJ
    return 1 if (disp == 'attachment' or has_name) else 0


def _attachment_count(raw_bytes):
    """Nombre de pièces jointes déduit du BODYSTRUCTURE (sans télécharger le corps).
    Best-effort : renvoie None si indéterminable (jamais d'exception vers l'appelant)."""
    try:
        idx = raw_bytes.upper().find(b'BODYSTRUCTURE')
        if idx < 0:
            return None
        blob = _extract_parens(raw_bytes, idx)
        if not blob:
            return None
        toks = _tokenize_bs(blob)
        return _count_attachments(toks[0]) if toks else None
    except Exception:
        return None


def fetch_submissions(config, folder=None):
    """Liste les demandes d'un dossier IMAP.
    `folder=None` → dossier des demandes en attente (IMAP_FOLDER) ;
    passer `config.IMAP_PROCESSED_FOLDER` pour lister les demandes archivées."""
    conn = _connect(config)
    try:
        conn.select(folder or config.IMAP_FOLDER)
        status, data = conn.search(None, *_search_criteria(config))
        if status != 'OK':
            return []

        submissions = []
        for uid in data[0].split():
            # LISTE = en-têtes SEULEMENT (rapide) : ne PAS télécharger le corps ni les
            # pièces jointes de chaque message. Le corps est chargé à la demande, au clic
            # « Voir » (cf. get_submission / route submission_preview). Sinon lister N
            # demandes = rapatrier N emails entiers, PJ comprises → très lent à l'échelle.
            # En-têtes + BODYSTRUCTURE : la BODYSTRUCTURE décrit la structure MIME
            # (donc le nombre de PJ) SANS télécharger le corps ni les pièces jointes →
            # la liste reste rapide même à grande échelle.
            status, msg_data = conn.fetch(uid, '(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)] BODYSTRUCTURE)')
            if status != 'OK' or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            name, addr = parseaddr(_decode(msg.get('From', '')))

            # Compter les PJ depuis la métadonnée BODYSTRUCTURE (best-effort).
            meta = b' '.join(p[0] if isinstance(p, tuple) else p
                             for p in msg_data if p and (isinstance(p, bytes) or isinstance(p, tuple)))
            att_count = _attachment_count(meta)

            submissions.append({
                'uid': uid.decode(),
                'from_name': name,
                'from_email': addr,
                'subject': _decode(msg.get('Subject', '')),
                'date': _fmt_date(msg.get('Date', '')),
                'attachment_count': att_count,
                'message_id': (msg.get('Message-ID') or '').strip(),
            })

        # Plus récent en premier
        submissions.reverse()
        return submissions
    finally:
        conn.logout()


def get_submission(config, uid, folder=None):
    """Récupère le détail complet (corps + pièces jointes avec contenu) d'une demande.
    `folder` permet de lire une demande ARCHIVÉE (IMAP_PROCESSED_FOLDER)."""
    conn = _connect(config)
    try:
        conn.select(folder or config.IMAP_FOLDER)
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
            'date': _fmt_date(msg.get('Date', '')),
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
