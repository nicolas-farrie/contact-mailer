"""
Module d'envoi d'emails avec rate-limiting et file d'attente.
"""
import smtplib
import ssl
import time
import email
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from pathlib import Path
from datetime import datetime
import re
import json


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
            result = text
            for key, value in data.items():
                result = result.replace(f'{{{key}}}', str(value or ''))
                result = result.replace(f'{{{{ {key} }}}}', str(value or ''))
            return result

        subject = replace_vars(self.subject, contact)
        body_text = replace_vars(self.body_text, contact)
        body_html = replace_vars(self.body_html, contact) if self.body_html else None

        # Ajouter le footer de désabonnement
        if unsubscribe_url:
            if body_text:
                body_text += f'\n\n---\nPour vous désabonner : {unsubscribe_url}'
            if body_html:
                body_html += (
                    '<hr><p style="font-size:14px;color:#999;">'
                    f'Pour vous désabonner : <a href="{unsubscribe_url}">cliquer ici</a></p>'
                )

        return (subject, body_text, body_html)


class MailQueue:
    """File d'attente persistante pour les envois"""

    def __init__(self, db_path: str = "data/mail_queue.json"):
        self.db_path = Path(db_path)
        self.queue = []
        self.campaigns = {}  # {campaign_id: {subject, body}}
        self._load()

    def _load(self):
        if self.db_path.exists():
            with open(self.db_path, 'r') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    self.queue = data.get('queue', [])
                    self.campaigns = data.get('campaigns', {})
                else:
                    # Migration depuis l'ancien format (liste simple)
                    self.queue = data
                    self.campaigns = {}

    def save(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.db_path, 'w') as f:
            json.dump({
                'queue': self.queue,
                'campaigns': self.campaigns
            }, f, indent=2, default=str)

    def set_campaign_template(self, campaign_id: str, subject: str, body: str, format: str = 'text',
                              sent_by: str = None, include_unsubscribe: bool = False):
        """Stocke le sujet, corps et format du mail pour une campagne"""
        data = {'subject': subject, 'body': body, 'format': format,
                'include_unsubscribe': include_unsubscribe}
        if sent_by:
            data['sent_by'] = sent_by
        self.campaigns[campaign_id] = data
        self.save()

    def get_campaign_template(self, campaign_id: str) -> dict:
        """Récupère le template d'une campagne"""
        return self.campaigns.get(campaign_id, {})

    def add(self, contact: dict, campaign_id: str):
        self.queue.append({
            'id': len(self.queue) + 1,
            'campaign_id': campaign_id,
            'contact': contact,
            'status': 'pending',  # pending, sent, error
            'attempts': 0,
            'error': None,
            'sent_at': None,
            'created_at': datetime.now().isoformat()
        })
        self.save()

    def get_pending(self, campaign_id: str = None):
        return [
            item for item in self.queue
            if item['status'] == 'pending'
            and (campaign_id is None or item['campaign_id'] == campaign_id)
        ]

    def mark_sent(self, item_id: int):
        for item in self.queue:
            if item['id'] == item_id:
                item['status'] = 'sent'
                item['sent_at'] = datetime.now().isoformat()
                break
        self.save()

    def mark_error(self, item_id: int, error: str):
        for item in self.queue:
            if item['id'] == item_id:
                item['status'] = 'error'
                item['attempts'] += 1
                item['error'] = error
                break
        self.save()

    def reset_errors(self, campaign_id: str = None):
        """Remet les erreurs en pending pour retry"""
        for item in self.queue:
            if item['status'] == 'error':
                if campaign_id is None or item['campaign_id'] == campaign_id:
                    item['status'] = 'pending'
                    item['error'] = None
        self.save()

    def get_stats(self, campaign_id: str = None):
        items = [i for i in self.queue if campaign_id is None or i['campaign_id'] == campaign_id]
        return {
            'total': len(items),
            'pending': len([i for i in items if i['status'] == 'pending']),
            'sent': len([i for i in items if i['status'] == 'sent']),
            'error': len([i for i in items if i['status'] == 'error'])
        }

    def get_campaigns_list(self):
        """Retourne la liste des campagnes avec stats et template, triées par date décroissante."""
        campaign_ids = set(item['campaign_id'] for item in self.queue)
        campaigns = []
        for cid in campaign_ids:
            stats = self.get_stats(cid)
            template = self.get_campaign_template(cid)
            # Extraire la date depuis le campaign_id (format: nom_YYYYMMDD_HHMMSS)
            parts = cid.rsplit('_', 2)
            date_str = ''
            if len(parts) >= 3:
                try:
                    date_str = datetime.strptime(
                        f"{parts[-2]}_{parts[-1]}", '%Y%m%d_%H%M%S'
                    ).strftime('%d/%m/%Y %H:%M')
                except ValueError:
                    date_str = ''
            campaigns.append({
                'id': cid,
                'date': date_str,
                'stats': stats,
                'template': template,
            })
        # Trier par ID décroissant (les plus récentes en premier)
        campaigns.sort(key=lambda c: c['id'], reverse=True)
        return campaigns

    def clear(self, campaign_id: str = None):
        if campaign_id:
            self.queue = [i for i in self.queue if i['campaign_id'] != campaign_id]
        else:
            self.queue = []
        self.save()


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
                     unsubscribe_url: str = None) -> bool:
        """Envoie un email unique. Retourne True si succès."""
        from email.utils import formatdate, make_msgid

        try:
            msg = MIMEMultipart('alternative') if body_html else MIMEText(body_text, 'plain', 'utf-8')

            msg['Subject'] = subject
            msg['From'] = formataddr((self.sender_name, self.sender_email))
            msg['To'] = to_email
            msg['Date'] = formatdate(localtime=True)
            msg['Message-ID'] = make_msgid(domain=self.sender_email.split('@')[1])
            msg['Content-Language'] = 'fr'

            if unsubscribe_url:
                msg['List-Unsubscribe'] = f'<{unsubscribe_url}>'
                msg['List-Unsubscribe-Post'] = 'List-Unsubscribe=One-Click'

            if body_html:
                msg.attach(MIMEText(body_text, 'plain', 'utf-8'))
                msg.attach(MIMEText(body_html, 'html', 'utf-8'))

            context = ssl.create_default_context()

            if self.use_tls:
                with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.sender_email, to_email, msg.as_string())
            else:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, context=context) as server:
                    server.login(self.smtp_user, self.smtp_password)
                    server.sendmail(self.sender_email, to_email, msg.as_string())

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
        queue = MailQueue()
        stats = queue.get_stats(args.campaign)
        print(f"Total: {stats['total']}")
        print(f"En attente: {stats['pending']}")
        print(f"Envoyés: {stats['sent']}")
        print(f"Erreurs: {stats['error']}")

    elif args.command == 'clear':
        queue = MailQueue()
        queue.clear(args.campaign)
        print("File vidée.")

    else:
        parser.print_help()
