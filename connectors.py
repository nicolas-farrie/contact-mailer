"""Socle commun des connecteurs externes (NOÉ, Seafile, BookStack).

Chaque service garde son module client (`noe.py`, `seafile.py`, `bookstack.py`) ; ce
fichier n'apporte que ce qui leur est commun : savoir se décrire et dire s'ils sont
configurés. C'est ce que la page Intégrations affiche, sans rien connaître d'aucun
service en particulier.

Volontairement minimal : pas de chargement dynamique ni de points d'entrée. Trois
connecteurs se déclarent à la main sans difficulté, et un registre explicite se lit
d'un coup d'œil.

Le **sens** compte autant que l'état : Seafile et BookStack *poussent* les contacts vers
un outil externe, NOÉ *tire* des bénévoles vers la base. Deux gestes très différents pour
qui les utilise, d'où `direction`.
"""

from config import Config

PUSH = 'push'   # contact-mailer → service externe
PULL = 'pull'   # service externe → contact-mailer

DIRECTION_LABELS = {
    PUSH: 'Pousse les contacts vers',
    PULL: 'Récupère les contacts depuis',
}


class Connector:
    """Base commune : un connecteur sait se nommer et dire s'il est utilisable.

    Sous-classer et renseigner `name`, `label`, `direction`, `description`, puis
    redéfinir `required_settings` (les variables d'environnement sans lesquelles rien
    n'est possible). `status()` suffit à la page Intégrations.
    """

    name = ''            # identifiant stable, sert aussi de `provider` dans ExternalIdentity
    label = ''           # nom affiché
    direction = PUSH
    description = ''
    doc_url = ''

    #: Variables de configuration indispensables — noms d'attributs de Config.
    required_settings = ()

    def missing_settings(self):
        """Les réglages absents, pour dire quoi ajouter au .env plutôt qu'un vague échec."""
        return [key for key in self.required_settings
                if not (getattr(Config, key, '') or '').strip()]

    def is_configured(self):
        return not self.missing_settings()

    def target(self):
        """Ce à quoi ce connecteur est relié (URL, projet…), ou '' si non configuré."""
        return ''

    def status(self):
        """État affichable — sans appel réseau : la page doit s'ouvrir même service éteint.

        Une connexion réellement vivante ne se vérifie qu'en appelant le service, ce que
        font les pages de chaque connecteur, à la demande.
        """
        return {
            'name': self.name,
            'label': self.label,
            'direction': self.direction,
            'direction_label': DIRECTION_LABELS.get(self.direction, ''),
            'description': self.description,
            'doc_url': self.doc_url,
            'configured': self.is_configured(),
            'missing': self.missing_settings(),
            'target': self.target(),
        }


class SeafileConnector(Connector):
    name = 'seafile'
    label = 'Seafile'
    direction = PUSH
    description = ("Crée les comptes des contacts sur votre Seafile et les range dans "
                   "des groupes, pour partager des fichiers avec une liste.")
    required_settings = ('SEAFILE_URL', 'SEAFILE_TOKEN')

    def target(self):
        return Config.SEAFILE_URL or ''


class BookstackConnector(Connector):
    name = 'bookstack'
    label = 'BookStack'
    direction = PUSH
    description = ("Crée les comptes des contacts sur votre BookStack avec un rôle "
                   "donné, pour ouvrir l'accès à une documentation.")
    required_settings = ('BOOKSTACK_URL', 'BOOKSTACK_TOKEN_ID', 'BOOKSTACK_TOKEN_SECRET')

    def target(self):
        return Config.BOOKSTACK_URL or ''


class NoeConnector(Connector):
    name = 'noe'
    label = 'NOÉ'
    direction = PULL
    description = ("Alimente vos listes depuis les bénévoles d'un festival géré avec "
                   "NOÉ : un pôle (accueil, restauration…) devient une liste.")
    doc_url = 'https://get.noe-app.io/fr/docs/api/'
    required_settings = ('NOE_URL', 'NOE_TOKEN', 'NOE_PROJECT_ID')

    def target(self):
        return Config.NOE_URL or ''


#: Registre parcouru par la page Intégrations. L'ordre est celui de l'affichage.
CONNECTORS = [
    NoeConnector(),
    SeafileConnector(),
    BookstackConnector(),
]


def get_connector(name):
    """Le connecteur portant ce nom, ou None."""
    return next((c for c in CONNECTORS if c.name == name), None)


def all_status():
    """L'état de tous les connecteurs, prêt pour le rendu."""
    return [c.status() for c in CONNECTORS]
