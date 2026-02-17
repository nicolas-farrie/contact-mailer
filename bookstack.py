"""Client API BookStack et fonction de push des contacts."""

import requests


class BookstackClient:
    """Client pour l'API REST BookStack."""

    def __init__(self, base_url, token_id, token_secret):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Token {token_id}:{token_secret}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

    def _request(self, method, endpoint, **kwargs):
        """Requête centralisée avec gestion d'erreurs."""
        url = f'{self.base_url}/api/{endpoint.lstrip("/")}'
        try:
            resp = self.session.request(method, url, timeout=30, **kwargs)
        except requests.ConnectionError:
            raise RuntimeError(f'Impossible de se connecter à {self.base_url}')
        except requests.Timeout:
            raise RuntimeError(f'Timeout lors de la requête vers {self.base_url}')

        if resp.status_code == 401:
            raise RuntimeError('Authentification BookStack refusée (token invalide)')
        if resp.status_code == 403:
            raise RuntimeError('Permission BookStack insuffisante pour cette opération')
        if not resp.ok:
            # Extraire le message d'erreur de BookStack si disponible
            try:
                detail = resp.json().get('error', {}).get('message', resp.text[:200])
            except Exception:
                detail = resp.text[:200]
            raise RuntimeError(f'BookStack {resp.status_code}: {detail}')
        return resp.json()

    def list_roles(self):
        """GET /api/roles - liste tous les rôles."""
        return self._request('GET', 'roles')

    def list_users(self):
        """GET /api/users avec pagination complète."""
        users = []
        offset = 0
        count = 100
        while True:
            data = self._request('GET', f'users?count={count}&offset={offset}')
            users.extend(data.get('data', []))
            total = data.get('total', 0)
            offset += count
            if offset >= total:
                break
        return users

    def get_user(self, user_id):
        """GET /api/users/{id} - détail avec rôles."""
        return self._request('GET', f'users/{user_id}')

    def create_user(self, name, email, roles, send_invite=True, language='fr'):
        """POST /api/users - crée un utilisateur."""
        payload = {
            'name': name,
            'email': email,
            'roles': roles,
            'send_invite': send_invite,
            'language': language,
        }
        return self._request('POST', 'users', json=payload)

    def update_user(self, user_id, roles):
        """PUT /api/users/{id} - met à jour les rôles."""
        payload = {'roles': roles}
        return self._request('PUT', f'users/{user_id}', json=payload)


def push_contacts_to_bookstack(client, contacts, role_id, send_invite=True):
    """Pousse une liste de contacts vers BookStack avec un rôle donné.

    Args:
        client: BookstackClient configuré
        contacts: liste d'objets Contact (modèle SQLAlchemy)
        role_id: ID du rôle BookStack à attribuer
        send_invite: envoyer une invitation par email aux nouveaux comptes

    Returns:
        dict avec clés created, updated, skipped, errors (liste de messages)
    """
    result = {'created': 0, 'updated': 0, 'skipped': 0, 'errors': []}

    # Récupérer tous les users BS (lookup par email)
    bs_users = client.list_users()
    email_to_user = {}
    for u in bs_users:
        email_lower = u.get('email', '').lower()
        if email_lower:
            email_to_user[email_lower] = u

    for contact in contacts:
        email = contact.email.strip().lower()
        name = f'{contact.prenom} {contact.nom}'.strip() or email

        try:
            bs_user = email_to_user.get(email)

            if bs_user:
                # User existe -> vérifier s'il a déjà le rôle
                detail = client.get_user(bs_user['id'])
                current_roles = [r['id'] for r in detail.get('roles', [])]

                if role_id in current_roles:
                    result['skipped'] += 1
                else:
                    new_roles = current_roles + [role_id]
                    client.update_user(bs_user['id'], new_roles)
                    result['updated'] += 1
            else:
                # User n'existe pas -> créer avec invitation
                client.create_user(name, email, [role_id], send_invite=send_invite)
                result['created'] += 1

        except Exception as e:
            result['errors'].append(f'{email}: {e}')

    return result
