from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timezone
import uuid

db = SQLAlchemy()


def utcnow():
    """UTC « naïf » (sans tzinfo), en remplacement de datetime.utcnow() (déprécié
    depuis Python 3.12). Conserve la sémantique naive-UTC utilisée partout dans le
    projet (colonnes `DateTime` sans timezone, comparaisons avec des datetimes naïfs)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

# Table d'association contacts <-> listes (many-to-many)
contact_liste = db.Table(
    'contact_liste',
    db.Column('contact_id', db.Integer, db.ForeignKey('contact.id'), primary_key=True),
    db.Column('liste_id', db.Integer, db.ForeignKey('liste.id'), primary_key=True)
)


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(255), nullable=False, unique=True, default=lambda: str(uuid.uuid4()))
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), nullable=False, index=True)
    civilite = db.Column(db.String(40))   # identité / formule d'appel (Madame, Monsieur, Mx…)
    genre = db.Column(db.String(20), default='Inclusif')   # accord grammatical (Féminin/Masculin/Inclusif) — clé stable {genre==…} ; défaut inclusif (jamais vide)
    titre = db.Column(db.String(50))
    telephone = db.Column(db.String(20))
    organisation = db.Column(db.String(200))
    adresse_rue = db.Column(db.String(200))
    adresse_complement = db.Column(db.String(200))
    adresse_ville = db.Column(db.String(100))
    adresse_cp = db.Column(db.String(20))
    adresse_region = db.Column(db.String(100))
    adresse_pays = db.Column(db.String(100))
    source = db.Column(db.String(100), default='Manuel')
    notes = db.Column(db.Text)
    custom_fields = db.Column(db.JSON)   # {fieldName: valeur} — champs personnalisés (cf. CustomFieldDefinition)
    seafile_temp_pwd = db.Column(db.String(100), nullable=True)
    is_unsubscribed = db.Column(db.Boolean, default=False)
    unsubscribed_at = db.Column(db.DateTime, nullable=True)
    has_bounced = db.Column(db.Boolean, default=False, nullable=False)
    bounced_at = db.Column(db.DateTime, nullable=True)
    is_deleted = db.Column(db.Boolean, default=False, nullable=False)
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # Traçabilité
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])
    deleted_by = db.relationship('User', foreign_keys=[deleted_by_id])

    # Relation many-to-many avec les listes
    listes = db.relationship('Liste', secondary=contact_liste, back_populates='contacts')

    def __repr__(self):
        return f'<Contact {self.prenom} {self.nom}>'

    def to_dict(self):
        data = {
            'id': self.id,
            'uid': self.uid,
            'nom': self.nom,
            'prenom': self.prenom,
            'civilite': self.civilite,
            'genre': self.genre,
            'titre': self.titre,
            'email': self.email,
            'telephone': self.telephone,
            'organisation': self.organisation,
            'adresse_rue': self.adresse_rue,
            'adresse_complement': self.adresse_complement,
            'adresse_ville': self.adresse_ville,
            'adresse_cp': self.adresse_cp,
            'adresse_region': self.adresse_region,
            'adresse_pays': self.adresse_pays,
            'source': self.source,
            'notes': self.notes,
            'seafile_temp_pwd': self.seafile_temp_pwd,
            'seafile_password': self.seafile_temp_pwd,  # alias pour templates mailing
            'listes': [l.nom for l in self.listes]
        }
        # Champs personnalisés aplatis → variables de fusion {key} (sans écraser une clé cœur)
        for key, value in (self.custom_fields or {}).items():
            data.setdefault(key, value)
        return data


class Liste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=utcnow)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)   # archivage réversible
    color = db.Column(db.String(9), nullable=True)                       # pastille choisie (#rrggbb)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id])

    # Relation many-to-many avec les contacts
    contacts = db.relationship('Contact', secondary=contact_liste, back_populates='listes')

    def __repr__(self):
        return f'<Liste {self.nom}>'

    @property
    def active_contacts(self):
        return [c for c in self.contacts if not c.is_deleted]

    @property
    def count(self):
        return sum(1 for c in self.contacts if not c.is_deleted)

    @property
    def joignables(self):
        """Contacts actifs (non supprimés) ET non désabonnés = destinataires réels."""
        return sum(1 for c in self.contacts if not c.is_deleted and not c.is_unsubscribed)

    @property
    def is_fed(self):
        """Vrai si une source externe alimente cette liste (son contenu est un reflet)."""
        return self.source is not None

    @property
    def sync_label(self):
        """« il y a 12 min » depuis la dernière synchronisation, ou '' si liste libre."""
        if self.source is None:
            return ''
        from helpers import since_label
        return since_label(self.source.last_sync_at) or 'jamais'

    @property
    def source_label(self):
        """Nom affichable de la source, demandé au registre — jamais écrit dans un template."""
        from helpers import list_source_label
        return list_source_label(self)


class ListSource(db.Model):
    """Source externe qui alimente une liste — son contenu devient un reflet.

    Générique par construction : `provider` est l'identifiant d'un connecteur (cf.
    connectors.py), jamais un nom écrit en dur ailleurs. Une liste alimentée depuis les
    groupes de Seafile ou les rôles de BookStack s'exprimerait de la même façon ; le
    cœur de l'application ne connaît que la notion de « liste alimentée ».

    **Une liste n'a qu'une seule source, et c'est un invariant, pas une limite d'étape.**
    Deux sources voudraient dire deux maîtres, donc plus de maître du tout : lorsqu'une
    personne est présente dans l'une et absente de l'autre, aucune règle de retrait ne
    peut trancher sans arbitraire. D'où UNIQUE(liste_id).

    `ref` est la clé côté source (« Restauration ») et `instance` l'installation d'où
    elle vient (l'id du projet NOÉ) : deux festivals ne se mélangent pas.
    """
    __tablename__ = 'list_source'
    id = db.Column(db.Integer, primary_key=True)
    liste_id = db.Column(db.Integer, db.ForeignKey('liste.id'), nullable=False,
                         unique=True, index=True)
    provider = db.Column(db.String(30), nullable=False)      # 'noe', 'seafile'…
    instance = db.Column(db.String(200), nullable=False, default='')
    ref = db.Column(db.String(200), nullable=False)          # clé du groupe côté source
    label = db.Column(db.String(200), nullable=False, default='')  # son nom affichable
    last_sync_at = db.Column(db.DateTime, nullable=True)
    last_error = db.Column(db.String(500), nullable=True)    # dernier échec, pour le dire
    created_at = db.Column(db.DateTime, default=utcnow)

    liste = db.relationship('Liste', backref=db.backref('source', uselist=False,
                                                        cascade='all, delete-orphan'))

    #: Au-delà, le reflet est jugé trop ancien pour partir en mailing sans y regarder.
    #: Six heures : plus large qu'un cycle de synchro (15 min), assez court pour qu'une
    #: journée de festival ne passe pas inaperçue.
    STALE_AFTER_HOURS = 6

    @property
    def is_stale(self):
        """Vrai si la dernière synchronisation est trop ancienne — ou n'a jamais eu lieu."""
        if self.last_sync_at is None:
            return True
        from datetime import timedelta
        return (utcnow() - self.last_sync_at) > timedelta(hours=self.STALE_AFTER_HOURS)

    def __repr__(self):
        return f'<ListSource {self.provider}:{self.ref} → liste {self.liste_id}>'


class User(UserMixin, db.Model):
    """Utilisateur avec rôles (admin/user)"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    email = db.Column(db.String(200))
    role = db.Column(db.String(20), default='user')
    is_moderator = db.Column(db.Boolean, default=False, nullable=False)  # reçoit les alertes de demandes de diffusion (≠ admin)
    moderation_signature = db.Column(db.String(120))  # pseudonyme public pour signer les diffusions modérées (optionnel)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=True)
    contact = db.relationship('Contact', foreign_keys=[contact_id])

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def display_name(self):
        if self.prenom and self.nom:
            return f"{self.prenom} {self.nom}"
        return self.username


class PreferenceForm(db.Model):
    __tablename__ = 'preference_form'
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    token = db.Column(db.String(32), unique=True, nullable=False, default=lambda: uuid.uuid4().hex)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    listes = db.relationship('PreferenceFormListe', back_populates='form',
                             order_by='PreferenceFormListe.ordre', cascade='all, delete-orphan')
    responses = db.relationship('PreferenceResponse', back_populates='form', cascade='all, delete-orphan')

    @property
    def real_responses(self):
        """Réponses réelles, hors envois de test (`is_test`). Base des verrous/compteurs."""
        return [r for r in self.responses if not r.is_test]


class PreferenceFormListe(db.Model):
    __tablename__ = 'preference_form_liste'
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('preference_form.id'), nullable=False)
    liste_id = db.Column(db.Integer, db.ForeignKey('liste.id'), nullable=False)
    label = db.Column(db.String(200), nullable=False)
    help_text = db.Column(db.Text, nullable=True)
    ordre = db.Column(db.Integer, default=0)
    block_id = db.Column(db.Integer, db.ForeignKey('form_block.id'), nullable=True)  # assembleur v2
    form = db.relationship('PreferenceForm', back_populates='listes')
    liste = db.relationship('Liste')


class PreferenceResponse(db.Model):
    __tablename__ = 'preference_response'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    form_id = db.Column(db.Integer, db.ForeignKey('preference_form.id'), nullable=False)
    submitted_at = db.Column(db.DateTime, default=utcnow)
    data = db.Column(db.JSON, nullable=True)   # payload v2 : {listes:[ids], survey:{question_id: réponse}}
    # Réponse issue d'un ENVOI TEST (« Envoi un test ») : parcours réel mais donnée
    # exclue partout où « réel » compte (verrou, compteurs, export). Bool aujourd'hui,
    # extensible en code (type de test) plus tard.
    is_test = db.Column(db.Boolean, default=False, nullable=False)
    contact = db.relationship('Contact')
    form = db.relationship('PreferenceForm', back_populates='responses')


# --- Formulaires v2 : assembleur de blocs ---

class FormBlock(db.Model):
    """Bloc typé d'un formulaire (assembleur v2). Chaque bloc porte son propre
    régime de sécurité : `listes`/`sondage` = accès direct ; `fiche` = OTP + validation admin."""
    __tablename__ = 'form_block'
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('preference_form.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)   # 'listes' | 'sondage' | 'fiche'
    ordre = db.Column(db.Integer, default=0)
    config = db.Column(db.JSON)   # ex bloc fiche : {"fields": ["telephone", "adresse_rue", ...]}
    form = db.relationship('PreferenceForm',
                           backref=db.backref('blocks', order_by='FormBlock.ordre',
                                              cascade='all, delete-orphan'))
    questions = db.relationship('SurveyQuestion', back_populates='block',
                                order_by='SurveyQuestion.ordre', cascade='all, delete-orphan')


class SurveyQuestion(db.Model):
    """Question d'un bloc « sondage » (hors base de données — stockage isolé dans
    PreferenceResponse.data ; n'écrit jamais sur la fiche du contact)."""
    __tablename__ = 'survey_question'
    id = db.Column(db.Integer, primary_key=True)
    block_id = db.Column(db.Integer, db.ForeignKey('form_block.id'), nullable=False)
    ordre = db.Column(db.Integer, default=0)
    label = db.Column(db.String(300), nullable=False)
    type = db.Column(db.String(20), default='texte_court')   # 'oui_non' | 'texte_court' | (extensible)
    config = db.Column(db.JSON)   # options éventuelles
    block = db.relationship('FormBlock', back_populates='questions')


class FieldProposal(db.Model):
    """Modification d'un champ de la FICHE proposée par un contact via un bloc « fiche »
    (cas 1). Rien n'est écrit sur la fiche tant qu'un admin n'a pas validé (onglet « À valider »)."""
    __tablename__ = 'field_proposal'
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('preference_form.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False)
    field_key = db.Column(db.String(64), nullable=False)   # clé fields.py (hors RESERVED_KEYS)
    old_value = db.Column(db.Text)     # valeur canonique au moment de la proposition
    new_value = db.Column(db.Text)     # valeur proposée par le contact
    status = db.Column(db.String(20), default='pending', nullable=False)   # pending | applied | rejected
    otp_verified = db.Column(db.Boolean, default=False, nullable=False)     # Phase 2 (OTP email)
    is_test = db.Column(db.Boolean, default=False, nullable=False)          # proposition issue d'un envoi test → exclue de « À valider »
    proposed_at = db.Column(db.DateTime, default=utcnow)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    contact = db.relationship('Contact')
    form = db.relationship('PreferenceForm')
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id])


class FormAccessCode(db.Model):
    """Code à usage unique (OTP) pour sécuriser le PRÉ-REMPLISSAGE d'un formulaire
    contenant un bloc « fiche » (Phase 2 / M9). Le code n'est JAMAIS transmis dans le
    mail du lien : il est envoyé à la demande, à l'ouverture de la page publique.
    Seul le hash est stocké."""
    __tablename__ = 'form_access_code'
    id = db.Column(db.Integer, primary_key=True)
    form_id = db.Column(db.Integer, db.ForeignKey('preference_form.id'), nullable=False, index=True)
    contact_uid = db.Column(db.String(64), nullable=False, index=True)
    code_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow, nullable=False)  # anti-flood (rate-limit)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)   # essais erronés (blocage au-delà d'un seuil)
    consumed = db.Column(db.Boolean, default=False, nullable=False)


class BookstackRole(db.Model):
    """Rôle importé depuis BookStack (référence locale)"""
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)  # ID venant de BS
    display_name = db.Column(db.String(200), nullable=False)
    synced_at = db.Column(db.DateTime, default=utcnow)


class Setting(db.Model):
    """Réglages applicatifs clé/valeur (app_name, login_bg, etc.)"""
    __tablename__ = 'settings'
    key = db.Column(db.String(64), primary_key=True)
    value = db.Column(db.Text, nullable=True)


class CustomFieldDefinition(db.Model):
    """Définition d'un champ personnalisé de contact, gérée par l'admin.

    Les valeurs sont stockées dans `Contact.custom_fields` (JSON), clées par `key`.
    Le registre `fields.py` (_custom_field_defs) consomme ces définitions actives."""
    __tablename__ = 'custom_field_definition'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(64), unique=True, nullable=False)   # fieldName (slug stable)
    display_name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(20), default='text')   # text|number|date|select|checkbox|textarea
    options = db.Column(db.JSON)                       # liste de choix (type 'select')
    help_text = db.Column(db.String(300))              # aide affichée sous le champ dans la fiche
    required = db.Column(db.Boolean, default=False, nullable=False)  # champ obligatoire à la saisie
    ordre = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=utcnow)


class MailCampaign(db.Model):
    """Template d'une campagne d'emailing (ex-`campaigns` du mail_queue.json).

    L'id est la chaîne de campagne existante (« {nom_liste}_{AAAAMMJJ_HHMMSS} »),
    conservée telle quelle pour compat avec le reste du code."""
    __tablename__ = 'mail_campaign'
    id = db.Column(db.String(255), primary_key=True, autoincrement=False)
    name = db.Column(db.String(200), nullable=True)   # nom lisible du mailing (≠ objet)
    subject = db.Column(db.Text, default='')
    body = db.Column(db.Text, default='')
    format = db.Column(db.String(10), default='text')
    sent_by = db.Column(db.String(200), nullable=True)
    include_unsubscribe = db.Column(db.Boolean, default=False)
    attachments = db.Column(db.JSON, nullable=True)   # liste de chemins
    liste_id = db.Column(db.Integer, nullable=True)          # compat : 1re liste sélectionnée
    liste_ids = db.Column(db.JSON, nullable=True)            # multi-listes (dédoublonnées à l'envoi)
    use_selection = db.Column(db.Boolean, default=False)     # unionne la « sélection courante » de l'auteur
    reply_to = db.Column(db.String(200), nullable=True)      # adresse de réponse (Reply-To) ≠ boîte d'envoi
    submission_id = db.Column(db.String(255), nullable=True)
    archived = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_template(self) -> dict:
        """Reconstruit le dict de template attendu par le reste du code
        (mêmes clés que l'ancien mail_queue.json : clés optionnelles omises
        si vides)."""
        data = {'subject': self.subject or '', 'body': self.body or '',
                'format': self.format or 'text',
                'include_unsubscribe': bool(self.include_unsubscribe),
                'name': self.name or ''}
        if self.sent_by:
            data['sent_by'] = self.sent_by
        if self.attachments:
            data['attachments'] = self.attachments
        if self.liste_id:
            data['liste_id'] = self.liste_id
        if self.liste_ids:
            data['liste_ids'] = self.liste_ids
        if self.use_selection:
            data['use_selection'] = True
        if self.reply_to:
            data['reply_to'] = self.reply_to
        if self.submission_id:
            data['submission_id'] = self.submission_id
        if self.archived:
            data['archived'] = True
        return data


class MailQueueItem(db.Model):
    """Un destinataire dans la file d'envoi (ex-`queue` du mail_queue.json).

    Le contact est stocké en SNAPSHOT (colonne JSON) : l'envoi utilise l'état du
    contact au moment de la mise en file, indépendamment des modifs ultérieures.
    L'id est auto-incrémenté → plus de collision possible (ancien bug len()+1)."""
    __tablename__ = 'mail_queue_item'
    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.String(255), index=True)
    contact = db.Column(db.JSON)   # snapshot Contact.to_dict()
    status = db.Column(db.String(12), default='pending', index=True)  # pending/sent/error/cancelled
    attempts = db.Column(db.Integer, default=0)
    error = db.Column(db.Text, nullable=True)          # erreur de l'essai COURANT (vidée au retry)
    last_error = db.Column(db.Text, nullable=True)     # dernière erreur connue, CONSERVÉE au retry (forensique)
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self) -> dict:
        """Même forme que les items de l'ancien mail_queue.json (dates en ISO)."""
        return {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'contact': self.contact,
            'status': self.status,
            'attempts': self.attempts or 0,
            'error': self.error,
            'last_error': self.last_error,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class ContactSend(db.Model):
    """Journal d'envoi PAR CONTACT : une ligne par email effectivement ENVOYÉ à un
    contact, pour une campagne. Fondation des segments « jamais mailé » / « déjà reçu
    la campagne X » et de l'historique d'envoi par contact.
    Léger, indexé, portable (pas de matching JSON) ; renseigné dans _run_send au moment
    de l'envoi réussi."""
    __tablename__ = 'contact_send'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False, index=True)
    campaign_id = db.Column(db.String(255), nullable=False, index=True)
    sent_at = db.Column(db.DateTime, default=utcnow, nullable=False)
    contact = db.relationship('Contact')


class ImportMapping(db.Model):
    """Association colonnes→champs RÉUTILISABLE pour l'import (import v2).

    Mémorise `{en-tête de colonne: clé de champ}` afin de rejouer l'association sur
    un fichier au même format. Réappliqué par correspondance de NOM de colonne
    (robuste à l'ordre / aux colonnes manquantes)."""
    __tablename__ = 'import_mapping'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    mapping = db.Column(db.JSON, nullable=False)   # {en-tête: clé_champ}
    created_at = db.Column(db.DateTime, default=utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class AuditLog(db.Model):
    """Journal d'audit (Tier 2) : traçabilité sécurité & données personnelles — « qui a
    fait quoi, quand ». PAS un suivi d'activité/navigation (cf. TODO « Logs & audit »).
    Append-only ; le username est snapshoté (survit à la suppression du compte) ; l'IP
    est optionnelle (toggle admin). Rétention bornée (purge auto, cf. audit.purge_old)."""
    __tablename__ = 'audit_log'
    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime, default=utcnow, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)  # nullable : login échoué = pas de compte
    username = db.Column(db.String(120))            # snapshot lisible
    action = db.Column(db.String(50), index=True)   # login, login_failed, password_changed, …
    target_type = db.Column(db.String(50), nullable=True)
    target_id = db.Column(db.String(100), nullable=True)
    details = db.Column(db.JSON, nullable=True)
    ip = db.Column(db.String(64), nullable=True)


class ExternalIdentity(db.Model):
    """Lien entre un contact et son identité dans un service externe (NOÉ, Seafile…).

    Sans elle, l'appariement à la resynchronisation repose sur l'email et le nom, que les
    gens font varier : une personne inscrite sur NOÉ avec son adresse perso et connue ici
    sous son adresse asso produit deux fiches, à chaque passage. Un identifiant stable
    rend l'import **idempotent** et survit aux changements d'email comme de nom.

    Table jointe plutôt qu'une colonne par service : ajouter un connecteur ne demande
    aucune migration, et un contact peut porter plusieurs identités — deux projets NOÉ,
    ou NOÉ et BookStack en même temps. D'où `instance`, qui distingue deux installations
    du même service (l'id de projet pour NOÉ, l'URL pour Seafile/BookStack).
    """
    __tablename__ = 'external_identity'
    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), nullable=False, index=True)
    provider = db.Column(db.String(30), nullable=False)      # noe | seafile | bookstack
    instance = db.Column(db.String(200), nullable=False, default='')  # projet NOÉ, URL… ('' si service unique)
    external_id = db.Column(db.String(200), nullable=False)  # ObjectId NOÉ, id BookStack, email Seafile
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    contact = db.relationship('Contact', backref=db.backref('external_identities',
                                                            cascade='all, delete-orphan'))

    __table_args__ = (
        # Une identité externe ne désigne qu'un seul contact : garde-fou contre le
        # double appariement, qui ferait diverger les synchronisations suivantes.
        db.UniqueConstraint('provider', 'instance', 'external_id',
                            name='uq_external_identity_ref'),
        # Recherche inverse « qui est ce bénévole ? », faite pour chaque ligne à chaque
        # synchro. Déclaré ici et pas seulement dans la migration : les bases créées par
        # db.create_all() (cf. app.py) doivent l'avoir aussi.
        db.Index('ix_external_identity_lookup', 'provider', 'instance', 'external_id'),
    )

    def __repr__(self):
        return f'<ExternalIdentity {self.provider}:{self.external_id} → contact {self.contact_id}>'


class NotifiedSubmission(db.Model):
    """Anti-doublon des notifications de demandes de diffusion : un `Message-ID` du mail
    reçu = une seule alerte aux modérateurs, même si le scan (périodique OU à l'ouverture
    de la page) repasse sur la même demande."""
    __tablename__ = 'notified_submission'
    message_id = db.Column(db.String(500), primary_key=True)
    notified_at = db.Column(db.DateTime, default=utcnow)


class ContactSegment(db.Model):
    """Segment nommé = jeu de conditions de filtre avancé réutilisable (P4b).

    Partagé (visible de tous), tracé par créateur — comme une Liste, mais c'est une
    DÉFINITION de filtre (dynamique), pas un ensemble figé de contacts. Les conditions
    sont stockées telles que produites par le constructeur : [{field, op, value}] +
    mode de jointure. « Appliquer » = rejouer ces conditions sur la page Contacts."""
    __tablename__ = 'contact_segment'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    conditions = db.Column(db.JSON, nullable=False)      # [{field, op, value|[lo,hi]}]
    join_mode = db.Column(db.String(4), default='and')   # 'and' | 'or' (mot 'join' réservé SQL)
    created_at = db.Column(db.DateTime, default=utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)


class ContactSetMember(db.Model):
    """Membre d'un ContactSet = ensemble de contacts identifié par une CLÉ de namespace.

    Socle réutilisable (cf. classe ContactSet dans contact_set.py) : la « sélection
    courante » de l'UI = clé `user:<id>` (singleton par utilisateur) ; d'autres usages
    en code (suivis opérationnels non-synchro) = `op:<nom>`. Algèbre ensembliste en SQL.
    PK composite (set_key, contact_id) → indexe naturellement les requêtes par set_key."""
    __tablename__ = 'contact_set_member'
    set_key = db.Column(db.String(80), primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('contact.id'), primary_key=True)
    added_at = db.Column(db.DateTime, default=utcnow)
