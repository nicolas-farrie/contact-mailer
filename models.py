from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import uuid

db = SQLAlchemy()

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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


class User(UserMixin, db.Model):
    """Utilisateur avec rôles (admin/user)"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    email = db.Column(db.String(200))
    role = db.Column(db.String(20), default='user')
    moderation_signature = db.Column(db.String(120))  # pseudonyme public pour signer les diffusions modérées (optionnel)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    proposed_at = db.Column(db.DateTime, default=datetime.utcnow)
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)  # anti-flood (rate-limit)
    expires_at = db.Column(db.DateTime, nullable=False)
    attempts = db.Column(db.Integer, default=0, nullable=False)   # essais erronés (blocage au-delà d'un seuil)
    consumed = db.Column(db.Boolean, default=False, nullable=False)


class BookstackRole(db.Model):
    """Rôle importé depuis BookStack (référence locale)"""
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)  # ID venant de BS
    display_name = db.Column(db.String(200), nullable=False)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
    error = db.Column(db.Text, nullable=True)
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
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
