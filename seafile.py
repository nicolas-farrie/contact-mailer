"""Client API Seafile et fonctions de synchronisation des contacts."""

import requests
import secrets
import string
from urllib.parse import quote


class SeafileClient:
    """Client pour l'API REST Seafile Community (v2.1)."""

    def __init__(self, base_url, token):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {token}',
            'Accept': 'application/json',
        })

    def _request(self, method, endpoint, **kwargs):
        """Requête centralisée avec gestion d'erreurs."""
        url = f'{self.base_url}/{endpoint.lstrip("/")}'
        try:
            resp = self.session.request(method, url, timeout=30, **kwargs)
        except requests.ConnectionError:
            raise RuntimeError(f'Impossible de se connecter à {self.base_url}')
        except requests.Timeout:
            raise RuntimeError(f'Timeout lors de la requête vers {self.base_url}')

        if resp.status_code == 401:
            raise RuntimeError('Authentification Seafile refusée (token invalide)')
        if resp.status_code == 403:
            raise RuntimeError('Permission Seafile insuffisante (compte admin requis)')
        if not resp.ok:
            try:
                detail = resp.json()
                msg = detail.get('error_msg') or detail.get('detail') or str(detail)[:200]
            except Exception:
                msg = resp.text[:200]
            raise RuntimeError(f'Seafile {resp.status_code}: {msg}')
        if resp.status_code == 204:
            return {}
        return resp.json()

    # === UTILISATEURS ===

    def list_users(self):
        """Retourne tous les utilisateurs (pagination automatique)."""
        users = []
        page = 1
        per_page = 100
        while True:
            data = self._request('GET', f'api/v2.1/admin/users/?page={page}&per_page={per_page}')
            if isinstance(data, list):
                users.extend(data)
                break
            # Seafile peut utiliser différentes clés selon la version
            batch = (data.get('data') or data.get('user_list') or
                     data.get('users') or [])
            users.extend(batch)
            if not data.get('next_page'):
                break
            page += 1
        return users

    def create_user(self, email, name, password):
        """Crée un utilisateur Seafile."""
        payload = {
            'email': email,
            'name': name,
            'password': password,
            'is_staff': False,
            'is_active': True,
        }
        return self._request('POST', 'api/v2.1/admin/users/', data=payload)

    def update_user(self, email, name=None, is_active=None):
        """Met à jour un utilisateur Seafile."""
        payload = {}
        if name is not None:
            payload['name'] = name
        if is_active is not None:
            payload['is_active'] = is_active
        encoded = quote(email, safe='')
        return self._request('PUT', f'api/v2.1/admin/users/{encoded}/', json=payload)

    # === GROUPES ===

    def list_groups(self):
        """Retourne tous les groupes."""
        data = self._request('GET', 'api/v2.1/admin/groups/?page=1&per_page=500')
        if isinstance(data, list):
            return data
        return data.get('groups', data.get('data', []))

    def create_group(self, name):
        """Crée un groupe Seafile."""
        return self._request('POST', 'api/v2.1/groups/', data={'name': name})

    def list_group_members(self, group_id):
        """Retourne les membres d'un groupe."""
        data = self._request('GET', f'api/v2.1/groups/{group_id}/members/')
        if isinstance(data, list):
            return data
        return data.get('members', data.get('data', []))

    def add_member_to_group(self, group_id, email):
        """Ajoute un membre à un groupe."""
        return self._request('POST', f'api/v2.1/groups/{group_id}/members/',
                              json={'email': email})


def generate_password(length=12):
    """Génère un mot de passe aléatoire sécurisé."""
    alphabet = string.ascii_letters + string.digits + '!@#$%'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def push_contacts_to_seafile(client, contacts, group_id=None):
    """Pousse une liste de contacts vers Seafile.

    - Crée les comptes manquants (mot de passe temporaire généré)
    - Met à jour le nom si le compte existe
    - Ajoute au groupe Seafile si group_id fourni

    Returns:
        dict avec clés created, updated, skipped, errors, passwords (email→mdp pour les nouveaux)
    """
    result = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': [], 'passwords': {}}

    # Index des users existants : lowercase → email exact stocké dans Seafile
    sf_users = client.list_users()
    email_map = {u['email'].lower(): u['email'] for u in sf_users}
    existing_emails = set(email_map.keys())

    # Index des membres du groupe si fourni
    group_member_emails = set()
    if group_id:
        members = client.list_group_members(group_id)
        group_member_emails = {m['email'].lower() for m in members}

    for contact in contacts:
        email = contact.email.strip().lower()
        name = f'{contact.prenom} {contact.nom}'.strip() or email
        # Email tel que stocké dans Seafile (peut différer de ce qu'on envoie)
        stored_email = email_map.get(email, email)

        try:
            if email in existing_emails:
                # Mise à jour du nom
                client.update_user(stored_email, name=name)
                result['updated'] += 1
            else:
                # Création avec mot de passe temporaire
                pwd = generate_password()
                try:
                    resp = client.create_user(email, name, pwd)
                    result['created'] += 1
                    result['passwords'][email] = pwd
                    # Récupère l'email réellement stocké depuis la réponse API
                    if isinstance(resp, dict) and resp.get('email'):
                        stored_email = resp['email']
                        email_map[email] = stored_email
                except RuntimeError as e:
                    if 'already exists' in str(e).lower():
                        # L'utilisateur existe déjà (list_users incomplet) : on met à jour
                        client.update_user(email, name=name)
                        result['updated'] += 1
                    else:
                        raise

            # Ajout au groupe si demandé et pas déjà membre
            if group_id and email not in group_member_emails:
                try:
                    client.add_member_to_group(group_id, stored_email)
                    group_member_emails.add(email)
                except Exception as e:
                    result['errors'].append(f'{email} (groupe): {e}')

        except Exception as e:
            result['errors'].append(f'{email}: {e}')

    return result
