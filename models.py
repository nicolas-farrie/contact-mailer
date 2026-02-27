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
    is_unsubscribed = db.Column(db.Boolean, default=False)
    unsubscribed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Traçabilité
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    updated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by = db.relationship('User', foreign_keys=[created_by_id])
    updated_by = db.relationship('User', foreign_keys=[updated_by_id])

    # Relation many-to-many avec les listes
    listes = db.relationship('Liste', secondary=contact_liste, back_populates='contacts')

    def __repr__(self):
        return f'<Contact {self.prenom} {self.nom}>'

    def to_dict(self):
        return {
            'id': self.id,
            'uid': self.uid,
            'nom': self.nom,
            'prenom': self.prenom,
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
            'listes': [l.nom for l in self.listes]
        }


class Liste(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relation many-to-many avec les contacts
    contacts = db.relationship('Contact', secondary=contact_liste, back_populates='listes')

    def __repr__(self):
        return f'<Liste {self.nom}>'

    @property
    def count(self):
        return len(self.contacts)


class User(UserMixin, db.Model):
    """Utilisateur avec rôles (admin/user)"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    nom = db.Column(db.String(100))
    prenom = db.Column(db.String(100))
    email = db.Column(db.String(200))
    role = db.Column(db.String(20), default='user')
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


class BookstackRole(db.Model):
    """Rôle importé depuis BookStack (référence locale)"""
    id = db.Column(db.Integer, primary_key=True, autoincrement=False)  # ID venant de BS
    display_name = db.Column(db.String(200), nullable=False)
    synced_at = db.Column(db.DateTime, default=datetime.utcnow)
