#!/usr/bin/env python3
"""
Migration : ajout du champ UID aux contacts et suppression de la contrainte unique sur email.

Usage :
    python tools/migrate_add_uid.py                    # migration réelle
    python tools/migrate_add_uid.py --dry-run          # simulation sans modification
    python tools/migrate_add_uid.py --db data/other.db # base personnalisée

Le script :
1. Crée un backup automatique de la base (data/contacts.db.bak.YYYYMMDD_HHMMSS)
2. Recrée la table contact avec :
   - colonne uid (TEXT 36, UNIQUE, NOT NULL) remplie avec uuid4
   - email sans contrainte UNIQUE (mais toujours NOT NULL + INDEX)
3. Préserve les IDs et les relations contact_liste
"""
import sqlite3
import shutil
import uuid
import sys
import os
from datetime import datetime

# Chemin par défaut de la base
DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'contacts.db')


def backup_db(db_path):
    """Crée une copie de sauvegarde horodatée."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.bak.{timestamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def check_already_migrated(conn):
    """Vérifie si la colonne uid existe déjà."""
    cursor = conn.execute("PRAGMA table_info(contact)")
    columns = [row[1] for row in cursor.fetchall()]
    return 'uid' in columns


def migrate(db_path, dry_run=False):
    """Exécute la migration."""
    if not os.path.exists(db_path):
        print(f"ERREUR : base introuvable : {db_path}")
        return False

    # Backup
    if not dry_run:
        backup_path = backup_db(db_path)
        print(f"Backup : {backup_path}")
    else:
        print("[DRY-RUN] Pas de backup créé")

    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")

    # Vérifier si déjà migré
    if check_already_migrated(conn):
        print("La colonne uid existe déjà. Migration non nécessaire.")
        conn.close()
        return True

    try:
        # 1. Lire les contacts existants (vérifier si les colonnes adresse existent déjà)
        col_cursor = conn.execute("PRAGMA table_info(contact)")
        existing_cols = [row[1] for row in col_cursor.fetchall()]
        has_adresse = 'adresse_rue' in existing_cols
        has_source = 'source' in existing_cols

        if has_adresse:
            source_col = "source" if has_source else "'Import'"
            cursor = conn.execute(f"SELECT id, nom, prenom, email, telephone, organisation, "
                                  f"adresse_rue, adresse_complement, adresse_ville, adresse_cp, adresse_region, adresse_pays, "
                                  f"{source_col}, notes, created_at, updated_at FROM contact")
        else:
            cursor = conn.execute("SELECT id, nom, prenom, email, telephone, organisation, "
                                  "NULL, NULL, NULL, NULL, NULL, NULL, "
                                  "'Import', notes, created_at, updated_at FROM contact")
        contacts = cursor.fetchall()
        print(f"Contacts existants : {len(contacts)}")

        # 2. Lire les relations contact_liste
        cursor = conn.execute("SELECT contact_id, liste_id FROM contact_liste")
        relations = cursor.fetchall()
        print(f"Relations contact_liste : {len(relations)}")

        # 3. Générer les UIDs
        contact_uids = {}
        for row in contacts:
            contact_uids[row[0]] = str(uuid.uuid4())

        if dry_run:
            print("\n[DRY-RUN] Aperçu des UIDs générés :")
            for row in contacts[:5]:
                print(f"  id={row[0]} email={row[3]} -> uid={contact_uids[row[0]]}")
            if len(contacts) > 5:
                print(f"  ... et {len(contacts) - 5} autres")
            print("\n[DRY-RUN] Aucune modification effectuée.")
            conn.close()
            return True

        # 4. Supprimer l'ancienne table et recréer
        conn.execute("DROP TABLE IF EXISTS contact_liste")
        conn.execute("DROP TABLE IF EXISTS contact")

        conn.execute("""
            CREATE TABLE contact (
                id INTEGER PRIMARY KEY,
                uid VARCHAR(255) NOT NULL UNIQUE,
                nom VARCHAR(100) NOT NULL,
                prenom VARCHAR(100) NOT NULL,
                email VARCHAR(200) NOT NULL,
                telephone VARCHAR(20),
                organisation VARCHAR(200),
                adresse_rue VARCHAR(200),
                adresse_complement VARCHAR(200),
                adresse_ville VARCHAR(100),
                adresse_cp VARCHAR(20),
                adresse_region VARCHAR(100),
                adresse_pays VARCHAR(100),
                source VARCHAR(100),
                notes TEXT,
                created_at DATETIME,
                updated_at DATETIME
            )
        """)
        conn.execute("CREATE INDEX ix_contact_email ON contact (email)")

        conn.execute("""
            CREATE TABLE contact_liste (
                contact_id INTEGER NOT NULL,
                liste_id INTEGER NOT NULL,
                PRIMARY KEY (contact_id, liste_id),
                FOREIGN KEY (contact_id) REFERENCES contact(id),
                FOREIGN KEY (liste_id) REFERENCES liste(id)
            )
        """)

        # 5. Réinsérer les contacts avec uid + adresse + source
        for row in contacts:
            # row: id, nom, prenom, email, telephone, organisation,
            #      adresse_rue, adresse_complement, adresse_ville, adresse_cp, adresse_region, adresse_pays,
            #      source, notes, created_at, updated_at
            cid = row[0]
            conn.execute(
                "INSERT INTO contact (id, uid, nom, prenom, email, telephone, organisation, "
                "adresse_rue, adresse_complement, adresse_ville, adresse_cp, adresse_region, adresse_pays, "
                "source, notes, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, contact_uids[cid], row[1], row[2], row[3], row[4], row[5],
                 row[6], row[7], row[8], row[9], row[10], row[11],
                 row[12], row[13], row[14], row[15])
            )

        # 6. Réinsérer les relations
        for contact_id, liste_id in relations:
            conn.execute(
                "INSERT INTO contact_liste (contact_id, liste_id) VALUES (?, ?)",
                (contact_id, liste_id)
            )

        conn.execute("PRAGMA foreign_keys = ON")
        conn.commit()
        print(f"Migration terminée : {len(contacts)} contacts migrés avec UID.")
        print(f"Contrainte unique sur email supprimée, index conservé.")

    except Exception as e:
        conn.rollback()
        print(f"ERREUR lors de la migration : {e}")
        conn.close()
        return False

    conn.close()
    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migration : ajout UID contacts')
    parser.add_argument('--db', default=DEFAULT_DB, help=f'Chemin de la base SQLite (défaut: {DEFAULT_DB})')
    parser.add_argument('--dry-run', action='store_true', help='Simulation sans modification')

    args = parser.parse_args()
    success = migrate(args.db, dry_run=args.dry_run)
    sys.exit(0 if success else 1)
