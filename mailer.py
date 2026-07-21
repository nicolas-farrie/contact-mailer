"""
Module d'envoi d'emails avec rate-limiting et file d'attente.
"""
import smtplib
import ssl
import time
import email
import base64
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr, make_msgid
from pathlib import Path
from datetime import datetime
import re
import json

from models import db, MailCampaign, MailQueueItem


_DATA_URI_RE = re.compile(r'data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=]+)')


def _extract_inline_images(body_html):
    """Remplace les images en data URI dans le HTML par des références cid:
    et retourne les parts MIME image correspondantes (à attacher en multipart/related).

    Nécessaire car un body HTML contenant une grosse data URI dépasse la taille
    de clip de la plupart des webmails (ex: ~102 Ko sur Gmail), ce qui fait
    disparaître tout le contenu visible du message."""
    images = []
    if not body_html:
        return body_html, images

    def replace(m):
        content_type, data = m.group(1), m.group(2)
        cid = make_msgid()[1:-1]
        img = MIMEImage(base64.b64decode(data), _subtype=content_type.split('/', 1)[1])
        img.add_header('Content-ID', f'<{cid}>')
        img.add_header('Content-Disposition', 'inline')
        images.append(img)
        return f'cid:{cid}'

    new_html = _DATA_URI_RE.sub(replace, body_html)
    return new_html, images


# URL nue (http/https) non précédée d'un caractère d'attribut/tag : évite de
# re-linker une URL déjà dans href="..." ou dans le texte visible d'un <a>.
_BARE_URL_RE = re.compile(r'(?<!["\'=>])(https?://[^\s<>"\']+)')


def _autolink_html(html):
    """Transforme les URLs nues d'un corps HTML en liens cliquables <a href>.

    Un lien collé en texte brut dans l'éditeur reste sinon du texte non
    cliquable dans la partie HTML du mail. Les URLs déjà dans un <a> sont
    ignorées (lookbehind). La ponctuation finale (. , ) …) est laissée hors du lien.
    """
    if not html:
        return html

    def _link(m):
        url = m.group(1)
        trail = ''
        while url and url[-1] in '.,;:!?)':
            trail = url[-1] + trail
            url = url[:-1]
        return f'<a href="{url}">{url}</a>{trail}'

    return _BARE_URL_RE.sub(_link, html)


class EmailTemplate:
    """Gère les templates d'email (texte, HTML ou .eml)"""

    def __init__(self, subject: str = "", body_text: str = "", body_html: str = None):
        self.subject = subject
        self.body_text = body_text
        self.body_html = body_html

    @classmethod
    def from_eml_file(cls, filepath: str) -> 'EmailTemplate':
        """Charge un template depuis un fichier .eml (brouillon Thunderbird)"""
        with open(filepath, 'rb') as f:
            msg = email.message_from_binary_file(f)

        subject = msg.get('Subject', '')
        # Décoder le sujet si encodé
        if subject:
            decoded = email.header.decode_header(subject)
            subject = ''.join(
                part.decode(enc or 'utf-8') if isinstance(part, bytes) else part
                for part, enc in decoded
            )

        body_text = ""
        body_html = None

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    body_text = part.get_payload(decode=True).decode('utf-8', errors='replace')
                elif content_type == 'text/html':
                    body_html = part.get_payload(decode=True).decode('utf-8', errors='replace')
        else:
            content_type = msg.get_content_type()
            payload = msg.get_payload(decode=True).decode('utf-8', errors='replace')
            if content_type == 'text/html':
                body_html = payload
            else:
                body_text = payload

        return cls(subject=subject, body_text=body_text, body_html=body_html)

    @classmethod
    def from_text_file(cls, filepath: str, subject: str = "") -> 'EmailTemplate':
        """Charge un template depuis un fichier texte"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Si le fichier commence par "Subject:", extraire le sujet
        if content.startswith('Subject:'):
            lines = content.split('\n', 1)
            subject = lines[0].replace('Subject:', '').strip()
            content = lines[1].strip() if len(lines) > 1 else ""

        return cls(subject=subject, body_text=content)

    @classmethod
    def from_html_file(cls, filepath: str, subject: str = "") -> 'EmailTemplate':
        """Charge un template depuis un fichier HTML"""
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Extraire le titre si présent
        title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
        if title_match and not subject:
            subject = title_match.group(1)

        return cls(subject=subject, body_text="", body_html=content)

    def render(self, contact: dict, unsubscribe_url: str = None) -> tuple:
        """
        Rend le template avec les données du contact.
        Retourne (subject, body_text, body_html)
        """
        def replace_vars(text: str, data: dict) -> str:
            if not text:
                return ''

            # Filet de sécurité : quand un lien contenant {uid} est inséré via la
            # boîte de dialogue de l'éditeur, TinyMCE URL-encode les accolades
            # ({uid} -> %7Buid%7D). On les redécode pour que la substitution de
            # variables ci-dessous retrouve bien {uid}, {prenom}, etc.
            text = text.replace('%7B', '{').replace('%7b', '{').replace('%7D', '}').replace('%7d', '}')

            # Pass 1 : variables simples {varname}
            def replace_simple(m):
                return str(data.get(m.group(1)) or '')

            result = re.sub(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}', replace_simple, text)

            # Pass 2 : conditionnels {condition:if_true[:if_false]}
            # condition : field (truthy) | field==val | field!=val
            def replace_cond(m):
                condition = m.group(1).strip()
                if_true  = m.group(2) or ''
                if_false = m.group(3) or ''

                if '==' in condition:
                    field, val = condition.split('==', 1)
                    test = str(data.get(field.strip()) or '').lower() == val.strip().lower()
                elif '!=' in condition:
                    field, val = condition.split('!=', 1)
                    test = str(data.get(field.strip()) or '').lower() != val.strip().lower()
                else:
                    test = bool(data.get(condition))

                return if_true if test else if_false

            result = re.sub(
                r'\{([a-zA-Z_][a-zA-Z0-9_]*(?:[!=]=[^:}]*)?):([^:}]*)(?::([^}]*))?\}',
                replace_cond,
                result
            )

            return result

        subject = replace_vars(self.subject, contact)
        body_text = replace_vars(self.body_text, contact)
        body_html = replace_vars(self.body_html, contact) if self.body_html else None

        # Rendre cliquables les URLs collées en texte brut (partie HTML uniquement) :
        # sinon un lien collé dans l'éditeur reste du texte non cliquable.
        if body_html:
            body_html = _autolink_html(body_html)

        # Ajouter le footer de désabonnement
        if unsubscribe_url:
            if body_text:
                body_text += f'\n\n---\nPour vous désabonner : {unsubscribe_url}'
            if body_html:
                body_html += (
                    '<hr><p style="font-size:14px;color:#999;">'
                    f'Pour vous désabonner : <a href="{unsubscribe_url}">cliquer ici</a></p>'
                )

        # Envelopper le HTML dans un document complet si ce n'est pas déjà le cas
        # (nécessaire pour les styles de listes, polices, etc.)
        if body_html and not body_html.strip().lower().startswith('<!doctype') \
                and not body_html.strip().lower().startswith('<html'):
            body_html = (
                '<!DOCTYPE html><html><head><meta charset="utf-8">'
                '<style>'
                'body{font-family:Arial,sans-serif;font-size:14px;line-height:1.6;color:#333;}'
                'ol,ul{padding-left:2em;margin:0.5em 0;}'
                'ol{list-style-type:decimal;}'
                'ul{list-style-type:disc;}'
                'ul ul{list-style-type:circle;}'
                'ul ul ul{list-style-type:square;}'
                'li,li.null{margin:0.25em 0;list-style-position:outside;}'
                'p{margin:0.5em 0;}'
                '</style></head><body>'
                + body_html
                + '</body></html>'
            )

        return (subject, body_text, body_html)


class MailQueue:
    """File d'attente persistante des envois (backend SQLite via SQLAlchemy).

    L'interface publique est identique à l'ancienne version fichier-JSON (les
    blueprints et templates sont inchangés), mais chaque opération est désormais
    une transaction courte sur la base : plus de réécriture d'un fichier global,
    plus de course entre workers, ids auto-incrémentés (fin du bug de collision).

    À utiliser dans un contexte d'application Flask (toutes les routes en ont un ;
    le CLI de ce module pousse le contexte explicitement)."""

    def __init__(self, db_path=None):
        # db_path est ignoré : conservé uniquement pour compat de signature avec
        # l'ancienne version fichier (personne ne le passe en pratique).
        pass

    def save(self):
        """Compat : les mutations committent déjà d'elles-mêmes. Commit sûr."""
        db.session.commit()

    # --- Templates de campagne ---

    def set_campaign_template(self, campaign_id: str, subject: str, body: str, format: str = 'text',
                              sent_by: str = None, include_unsubscribe: bool = False,
                              attachments: list = None, liste_id: int = None,
                              submission_id: str = None, liste_ids: list = None):
        """Crée ou met à jour le template (sujet, corps, format…) d'une campagne."""
        camp = db.session.get(MailCampaign, campaign_id)
        if camp is None:
            camp = MailCampaign(id=campaign_id)
            db.session.add(camp)
        camp.subject = subject
        camp.body = body
        camp.format = format
        camp.include_unsubscribe = include_unsubscribe
        camp.sent_by = sent_by
        camp.attachments = attachments or None
        camp.liste_id = liste_id
        camp.liste_ids = liste_ids
        camp.submission_id = submission_id
        db.session.commit()

    def get_campaign_template(self, campaign_id: str) -> dict:
        """Récupère le template d'une campagne ({} si inconnue)."""
        camp = db.session.get(MailCampaign, campaign_id)
        return camp.to_template() if camp else {}

    # --- Items de la file ---

    def add(self, contact: dict, campaign_id: str):
        db.session.add(MailQueueItem(campaign_id=campaign_id, contact=contact,
                                     status='pending'))
        db.session.commit()

    @property
    def queue(self):
        """Compat : liste de tous les items (mêmes dicts qu'avant), lue directement
        par certains blueprints (ex: mailing.queue)."""
        items = MailQueueItem.query.order_by(MailQueueItem.id).all()
        return [i.to_dict() for i in items]

    def get_pending(self, campaign_id: str = None):
        q = MailQueueItem.query.filter_by(status='pending')
        if campaign_id is not None:
            q = q.filter_by(campaign_id=campaign_id)
        return [i.to_dict() for i in q.order_by(MailQueueItem.id).all()]

    def mark_sent(self, item_id: int):
        item = db.session.get(MailQueueItem, item_id)
        if item:
            item.status = 'sent'
            item.sent_at = datetime.now()
            db.session.commit()

    def mark_error(self, item_id: int, error: str):
        item = db.session.get(MailQueueItem, item_id)
        if item:
            item.status = 'error'
            item.attempts = (item.attempts or 0) + 1
            item.error = error
            db.session.commit()

    def reset_errors(self, campaign_id: str = None):
        """Remet les erreurs en pending pour retry."""
        q = MailQueueItem.query.filter_by(status='error')
        if campaign_id is not None:
            q = q.filter_by(campaign_id=campaign_id)
        q.update({'status': 'pending', 'error': None}, synchronize_session=False)
        db.session.commit()

    def get_stats(self, campaign_id: str = None):
        q = db.session.query(MailQueueItem.status, db.func.count()).group_by(MailQueueItem.status)
        if campaign_id is not None:
            q = q.filter(MailQueueItem.campaign_id == campaign_id)
        by = dict(q.all())
        return {
            'total': sum(by.values()),
            'pending': by.get('pending', 0),
            'sent': by.get('sent', 0),
            'error': by.get('error', 0),
            'cancelled': by.get('cancelled', 0),
        }

    # --- Vues « campagnes » (dérivées des items, comme avant) ---

    def _campaign_ids(self):
        rows = db.session.query(MailQueueItem.campaign_id).distinct().all()
        return [r[0] for r in rows]

    def _build_campaign_entry(self, cid):
        template = self.get_campaign_template(cid)
        stats = self.get_stats(cid)
        parts = cid.rsplit('_', 2)
        date_str = ''
        if len(parts) >= 3:
            try:
                date_str = datetime.strptime(
                    f"{parts[-2]}_{parts[-1]}", '%Y%m%d_%H%M%S'
                ).strftime('%d/%m/%Y %H:%M')
            except ValueError:
                pass
        rows = (db.session.query(MailQueueItem.contact)
                .filter(MailQueueItem.campaign_id == cid,
                        MailQueueItem.status == 'sent').all())
        sent_emails = {(r[0] or {}).get('email', '') for r in rows}
        return {'id': cid, 'date': date_str, 'stats': stats,
                'template': template, 'sent_emails': sent_emails}

    def get_campaigns_list(self):
        """Campagnes non archivées, triées par date décroissante."""
        campaigns = [self._build_campaign_entry(cid) for cid in self._campaign_ids()
                     if not self.get_campaign_template(cid).get('archived')]
        campaigns.sort(key=lambda c: c['id'], reverse=True)
        return campaigns

    def get_archived_campaigns_list(self):
        """Campagnes archivées, triées par date décroissante."""
        campaigns = [self._build_campaign_entry(cid) for cid in self._campaign_ids()
                     if self.get_campaign_template(cid).get('archived')]
        campaigns.sort(key=lambda c: c['id'], reverse=True)
        return campaigns

    def archive_campaign(self, campaign_id: str):
        """Masque une campagne de l'historique et annule les envois en attente."""
        (MailQueueItem.query
         .filter_by(campaign_id=campaign_id, status='pending')
         .update({'status': 'cancelled'}, synchronize_session=False))
        camp = db.session.get(MailCampaign, campaign_id)
        if camp:
            camp.archived = True
        db.session.commit()

    def unarchive_campaign(self, campaign_id: str):
        """Remet une campagne dans l'historique et restaure les envois annulés."""
        (MailQueueItem.query
         .filter_by(campaign_id=campaign_id, status='cancelled')
         .update({'status': 'pending'}, synchronize_session=False))
        camp = db.session.get(MailCampaign, campaign_id)
        if camp:
            camp.archived = False
        db.session.commit()

    def clear(self, campaign_id: str = None):
        q = MailQueueItem.query
        if campaign_id:
            q = q.filter_by(campaign_id=campaign_id)
        q.delete(synchronize_session=False)
        db.session.commit()

    def delete_campaign(self, campaign_id: str):
        (MailQueueItem.query.filter_by(campaign_id=campaign_id)
         .delete(synchronize_session=False))
        camp = db.session.get(MailCampaign, campaign_id)
        if camp:
            db.session.delete(camp)
        db.session.commit()


class Mailer:
    """Envoi d'emails avec rate-limiting"""

    def __init__(self, smtp_host: str, smtp_port: int, smtp_user: str, smtp_password: str,
                 sender_email: str, sender_name: str = "", use_tls: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.sender_email = sender_email
        self.sender_name = sender_name
        self.use_tls = use_tls

    def send_single(self, to_email: str, subject: str, body_text: str, body_html: str = None,
                     unsubscribe_url: str = None, attachments: list = None,
                     return_path: str = None) -> bool:
        """Envoie un email unique. Retourne True si succès."""
        from email.utils import formatdate
        from email.mime.base import MIMEBase
        from email import encoders as email_encoders

        has_attachments = bool(attachments)
        body_html, inline_images = _extract_inline_images(body_html)
        has_inline_images = bool(inline_images)

        try:
            if has_attachments:
                msg = MIMEMultipart('mixed')
            elif body_html and has_inline_images:
                msg = MIMEMultipart('related')
            elif body_html:
                msg = MIMEMultipart('alternative')
            else:
                msg = MIMEText(body_text, 'plain', 'utf-8')

            msg['Subject'] = subject
            msg['From'] = formataddr((self.sender_name, self.sender_email))
            msg['To'] = to_email
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid(domain=self.sender_email.split('@')[1])
            msg['Content-Language'] = 'fr'

            if return_path:
                msg['Return-Path'] = f'<{return_path}>'

            if unsubscribe_url:
                msg['List-Unsubscribe'] = f'<{unsubscribe_url}>'
                msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'

            if body_html:
                if has_inline_images:
                    alt = MIMEMultipart('alternative')
                    alt.attach(MIMEText(body_text, 'plain', 'utf-8'))
                    alt.attach(MIMEText(body_html, 'html', 'utf-8'))
                    if has_attachments:
                        related = MIMEMultipart('related')
                        related.attach(alt)
                        for img in inline_images:
                            related.attach(img)
                        msg.attach(related)
                    else:
                        msg.attach(alt)
                        for img in inline_images:
                            msg.attach(img)
                elif has_attachments:
                    alt = MIMEMultipart('alternative')
                    alt.attach(MIMEText(body_text, 'plain', 'utf-8'))
                    alt.attach(MIMEText(body_html, 'html', 'utf-8'))
                    msg.attach(alt)
                else:
                    msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
                    msg.attach(MIMEText(body_html, 'html', 'utf-8'))
            elif has_attachments:
                msg.attach(MIMEText(body_text, 'plain', 'utf-8'))

            if has_attachments:
                # Pièces jointes
                for filepath in attachments:
                    filepath = Path(filepath)
                    if not filepath.exists():
                        continue
                    with open(filepath, 'rb') as f:
                        part = MIMEBase('application', 'octet-stream')
                        part.set_payload(f.read())
                    email_encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename="{filepath.name}"')
                    msg.attach(part)

            context = ssl.create_default_context()

            # L'expéditeur d'ENVELOPPE (MAIL FROM) détermine où reviennent les bounces.
            # Le header Return-Path seul ne suffit PAS — il faut le passer ici.
            envelope_from = return_path or self.sender_email

            if self.use_tls:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(envelope_from, to_email, msg.as_string())
            else:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(envelope_from, to_email, msg.as_string())

            return True

        except Exception as e:
            raise e

    def send_campaign(self, contacts: list, template: EmailTemplate, campaign_id: str,
                      rate_per_minute: int = 20, callback=None) -> dict:
        """
        Envoie une campagne à une liste de contacts.

        Args:
            contacts: Liste de dicts avec au moins 'email'
            template: EmailTemplate à utiliser
            campaign_id: Identifiant unique de la campagne
            rate_per_minute: Nombre d'emails par minute (rate-limiting)
            callback: Fonction appelée après chaque envoi (contact, success, error)

        Returns:
            Stats de la campagne
        """
        queue = MailQueue()

        # Ajouter tous les contacts à la file
        for contact in contacts:
            queue.add(contact, campaign_id)

        # Calculer le délai entre chaque envoi
        delay = 60.0 / rate_per_minute

        stats = {'sent': 0, 'errors': 0}
        pending = queue.get_pending(campaign_id)

        for item in pending:
            contact = item['contact']

            try:
                subject, body_text, body_html = template.render(contact)
                self.send_single(contact['email'], subject, body_text, body_html)
                queue.mark_sent(item['id'])
                stats['sent'] += 1

                if callback:
                    callback(contact, True, None)

            except Exception as e:
                queue.mark_error(item['id'], str(e))
                stats['errors'] += 1

                if callback:
                    callback(contact, False, str(e))

            # Rate limiting
            time.sleep(delay)

        return stats


# === CLI ===
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Contact Mailer - Envoi d\'emails')
    subparsers = parser.add_subparsers(dest='command')

    # Test de connexion SMTP
    test_parser = subparsers.add_parser('test', help='Tester la connexion SMTP')
    test_parser.add_argument('--host', required=True, help='Serveur SMTP')
    test_parser.add_argument('--port', type=int, default=587, help='Port SMTP')
    test_parser.add_argument('--user', required=True, help='Utilisateur SMTP')
    test_parser.add_argument('--password', required=True, help='Mot de passe SMTP')

    # Stats de la file
    stats_parser = subparsers.add_parser('stats', help='Afficher les stats de la file')
    stats_parser.add_argument('--campaign', help='ID de campagne (optionnel)')

    # Clear la file
    clear_parser = subparsers.add_parser('clear', help='Vider la file')
    clear_parser.add_argument('--campaign', help='ID de campagne (optionnel)')

    args = parser.parse_args()

    if args.command == 'test':
        print(f"Test de connexion à {args.host}:{args.port}...")
        try:
            context = ssl.create_default_context()
            with smtplib.SMTP(args.host, args.port) as server:
                server.starttls(context=context)
                server.login(args.user, args.password)
            print("✓ Connexion SMTP réussie !")
        except Exception as e:
            print(f"✗ Erreur : {e}")

    elif args.command == 'stats':
        # La file est en base : besoin d'un contexte d'application.
        from app import app as _flask_app
        with _flask_app.app_context():
            stats = MailQueue().get_stats(args.campaign)
        print(f"Total: {stats['total']}")
        print(f"En attente: {stats['pending']}")
        print(f"Envoyés: {stats['sent']}")
        print(f"Erreurs: {stats['error']}")

    elif args.command == 'clear':
        from app import app as _flask_app
        with _flask_app.app_context():
            MailQueue().clear(args.campaign)
        print("File vidée.")

    else:
        parser.print_help()
