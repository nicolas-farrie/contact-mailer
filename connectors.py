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

    # === ALIMENTATION DE LISTES ===
    # Un connecteur peut fournir des « groupes » (pôles NOÉ, groupes Seafile, rôles
    # BookStack…) dont chacun peut alimenter une liste. Le cœur de l'application ne
    # connaît que cette notion : il passe par le registre, jamais par un module de
    # service. Un connecteur qui n'alimente rien laisse can_feed_lists à False.

    can_feed_lists = False

    #: Libellé de l'entrée de menu vers ses groupes. « Bénévoles NOÉ » ne vaut que pour
    #: NOÉ : c'est au connecteur de nommer ce qu'il apporte, pas au template.
    feed_menu_label = ''

    def instance_key(self):
        """Identifie l'installation, pour ne pas mélanger deux sources du même service.

        L'id du projet pour NOÉ, l'URL pour un service unique par instance.
        """
        return self.target()

    #: Niveaux de regroupement proposés, s'il y en a plusieurs : [(clé, libellé)…].
    #: Le premier est celui présenté par défaut. Vide = un seul niveau, pas de bascule.
    LEVELS = ()

    def list_groups(self, level=None):
        """[{'ref', 'label', 'count'}] — les groupes proposables comme source.

        `ref` est la clé stable côté service, opaque pour l'appelant : le connecteur y
        met ce dont il a besoin pour retrouver le groupe plus tard (un niveau, un
        identifiant…). `label` est son nom affichable.
        """
        raise NotImplementedError

    def fetch_members(self, ref):
        """[{'email', 'prenom', 'nom', 'telephone'}] — les membres d'un groupe.

        Le format est celui qu'attend l'import : c'est au connecteur de traduire le
        vocabulaire de son service, pas à l'appelant de le connaître.
        """
        raise NotImplementedError

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
            'can_feed_lists': self.can_feed_lists,
            'feed_menu_label': self.feed_menu_label or self.label,
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

    can_feed_lists = True
    feed_menu_label = 'Bénévoles NOÉ'

    def target(self):
        return Config.NOE_URL or ''

    def instance_key(self):
        """Le projet NOÉ : deux festivals sur le même serveur ne se mélangent pas."""
        return Config.NOE_PROJECT_ID or ''

    def _client(self):
        from noe import NoeClient
        return NoeClient(Config.NOE_URL, Config.NOE_TOKEN, Config.NOE_PROJECT_ID)

    #: Niveaux de regroupement proposés. Les pôles d'abord : c'est la maille à laquelle
    #: on s'adresse aux bénévoles (« la restauration »), les missions servant quand un
    #: pôle est trop large pour un message ciblé.
    LEVELS = (('category', 'Pôles'), ('activity', 'Missions'))
    DEFAULT_LEVEL = 'category'

    @classmethod
    def parse_ref(cls, ref):
        """« activity:Chapeaux » → ('activity', 'Chapeaux').

        Le niveau voyage DANS la référence plutôt que dans une colonne dédiée : le cœur
        de l'application n'a pas à connaître une notion propre à NOÉ, et c'est au
        connecteur d'interpréter sa propre clé. Une référence sans préfixe vaut
        `category` — les listes rattachées avant l'introduction des missions continuent
        donc de fonctionner sans migration.
        """
        level, sep, name = (ref or '').partition(':')
        if sep and level in dict(cls.LEVELS):
            return level, name
        return cls.DEFAULT_LEVEL, ref or ''

    @classmethod
    def canonical_ref(cls, ref):
        """Ramène une référence à sa forme préfixée, même si elle a été stockée sans.

        Les listes rattachées avant l'introduction des missions portent « Restauration »
        et non « category:Restauration » : sans cette normalisation, elles cesseraient
        d'être reconnues comme déjà rattachées.
        """
        level, name = cls.parse_ref(ref)
        return f'{level}:{name}'

    def list_groups(self, level=None):
        """Les groupes du festival et leurs effectifs, au niveau demandé.

        Seuls ceux comptant au moins un bénévole, quel que soit le niveau : un festival
        déclare ses catégories et ses missions très en amont, lister les vides noierait
        celles où il y a quelqu'un à qui écrire (cf. build_group_index).
        """
        from noe import build_group_index
        level = level if level in dict(self.LEVELS) else self.DEFAULT_LEVEL
        index = build_group_index(self._client(), level=level)
        return [{'ref': f'{level}:{name}', 'label': name, 'count': len(members),
                 'level': level}
                for name, members in index.items()]

    def fetch_members(self, ref):
        """Les membres d'un groupe, le niveau étant lu dans la référence elle-même."""
        from noe import pull_contacts_from_noe
        level, name = self.parse_ref(ref)
        contacts, _stats = pull_contacts_from_noe(self._client(), name, level=level)
        return contacts


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
