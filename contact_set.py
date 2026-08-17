"""ContactSet — ensemble de contacts identifié par une CLÉ de namespace.

Objet réutilisable et instanciable adossé à la table `contact_set_member`. La
« sélection courante » de l'UI = `ContactSet.for_user(user_id)` (clé `user:<id>`,
singleton par utilisateur, persistée). D'autres usages en code (suivis opérationnels
non-synchro) = `ContactSet("op:<nom>")`. Algèbre ensembliste en SQL, portable.
"""
from models import db, Contact, ContactSetMember


class ContactSet:
    def __init__(self, key):
        if not key:
            raise ValueError('ContactSet: clé vide')
        self.key = str(key)

    @classmethod
    def for_user(cls, user_id):
        """Sélection courante d'un utilisateur (singleton, clé `user:<id>`)."""
        return cls(f'user:{user_id}')

    def __repr__(self):
        return f'<ContactSet {self.key} ({self.count()})>'

    # --- lecture ---
    def ids(self):
        """Ids bruts de l'ensemble (peut inclure des contacts depuis supprimés)."""
        return {r[0] for r in db.session.query(ContactSetMember.contact_id)
                .filter_by(set_key=self.key).all()}

    def contacts(self, order=None):
        """Query des contacts NON supprimés de l'ensemble."""
        q = (Contact.query
             .join(ContactSetMember, ContactSetMember.contact_id == Contact.id)
             .filter(ContactSetMember.set_key == self.key, Contact.is_deleted == False))
        return q.order_by(order) if order is not None else q.order_by(Contact.nom, Contact.prenom)

    def count(self):
        """Nombre de contacts NON supprimés (= ce qu'on affiche/actionne réellement)."""
        return self.contacts().count()

    # --- écriture (algèbre sur l'ensemble) ---
    def add(self, contact_ids):
        """∪ : ajoute les ids manquants. Renvoie le nombre réellement ajouté."""
        ids = {int(i) for i in contact_ids if i not in (None, '')}
        if not ids:
            return 0
        to_add = ids - self.ids()
        for cid in to_add:
            db.session.add(ContactSetMember(set_key=self.key, contact_id=cid))
        db.session.commit()
        return len(to_add)

    def remove(self, contact_ids):
        """∖ : retire les ids donnés. Renvoie le nombre retiré."""
        ids = {int(i) for i in contact_ids if i not in (None, '')}
        if not ids:
            return 0
        n = (ContactSetMember.query
             .filter(ContactSetMember.set_key == self.key, ContactSetMember.contact_id.in_(ids))
             .delete(synchronize_session=False))
        db.session.commit()
        return n

    def replace(self, contact_ids):
        """Remplace l'ensemble par les ids donnés."""
        self.clear()
        return self.add(contact_ids)

    def intersect(self, contact_ids):
        """∩ : ne garde que les ids présents dans `contact_ids`. Renvoie le nombre retiré."""
        keep = {int(i) for i in contact_ids if i not in (None, '')}
        return self.remove(self.ids() - keep)

    def clear(self):
        n = ContactSetMember.query.filter_by(set_key=self.key).delete(synchronize_session=False)
        db.session.commit()
        return n

    # --- algèbre entre deux ensembles ---
    def union(self, other):
        return self.add(other.ids())

    def difference(self, other):
        return self.remove(other.ids())

    def intersect_with(self, other):
        return self.intersect(other.ids())
