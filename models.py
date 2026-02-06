from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# Table d'association contacts <-> listes (many-to-many)
contact_liste = db.Table(
    'contact_liste',
    db.Column('contact_id', db.Integer, db.ForeignKey('contact.id'), primary_key=True),
    db.Column('liste_id', db.Integer, db.ForeignKey('liste.id'), primary_key=True)
)


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    prenom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)
    telephone = db.Column(db.String(20))
    organisation = db.Column(db.String(200))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relation many-to-many avec les listes
    listes = db.relationship('Liste', secondary=contact_liste, back_populates='contacts')

    def __repr__(self):
        return f'<Contact {self.prenom} {self.nom}>'

    def to_dict(self):
        return {
            'id': self.id,
            'nom': self.nom,
            'prenom': self.prenom,
            'email': self.email,
            'telephone': self.telephone,
            'organisation': self.organisation,
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
    """Utilisateur pour l'authentification simple"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
