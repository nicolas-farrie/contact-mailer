#!/usr/bin/env python3
"""
Migration : gestion multi-utilisateurs et traçabilité.

Usage :
    python tools/migrate_add_users.py                    # migration réelle
    python tools/migrate_add_users.py --dry-run          # simulation sans modification
    python tools/migrate_add_users.py --db data/other.db # base personnalisée

Le script :
1. Crée un backup automatique de la base
2. Table user : ajoute colonnes nom, prenom, email, role, is_active, created_at
3. Table contact : ajoute colonnes created_by_id, updated_by_id
4. Met role='admin' pour les utilisateurs existants
"""
import sqlite3
import shutil
import sys
import os
from datetime import datetime

DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', 'contacts.db')


def backup_db(db_path):
    """Crée une copie de sauvegarde horodatée."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{db_path}.bak.{timestamp}"
    shutil.copy2(db_path, backup_path)
    return backup_path


def get_table_columns(conn, table):
    """Retourne la liste des noms de colonnes d'une table."""
    cursor = conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def migrate(db_path, dry_run=False):
    """Exécute la migration."""
    if not os.path.exists(db_path):
        print(f"ERREUR : base introuvable : {db_path}")
        return False

    conn = sqlite3.connect(db_path)

    # Vérifier les tables existantes
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    if 'user' not in tables:
        print("ERREUR : table 'user' introuvable. Lancez l'application d'abord pour créer le schéma.")
        conn.close()
        return False

    user_cols = get_table_columns(conn, 'user')
    contact_cols = get_table_columns(conn, 'contact') if 'contact' in tables else []

    # Déterminer les modifications nécessaires
    user_additions = []
    for col, typedef in [
        ('nom', 'VARCHAR(100)'),
        ('prenom', 'VARCHAR(100)'),
        ('email', 'VARCHAR(200)'),
        ('role', "VARCHAR(20) DEFAULT 'user'"),
        ('is_active', 'BOOLEAN DEFAULT 1'),
        ('created_at', 'DATETIME'),
    ]:
        if col not in user_cols:
            user_additions.append((col, typedef))

    contact_additions = []
    if 'contact' in tables:
        for col, typedef in [
            ('created_by_id', 'INTEGER REFERENCES user(id)'),
            ('updated_by_id', 'INTEGER REFERENCES user(id)'),
        ]:
            if col not in contact_cols:
                contact_additions.append((col, typedef))

    if not user_additions and not contact_additions:
        print("Toutes les colonnes existent deja. Migration non necessaire.")
        conn.close()
        return True

    # Compter les utilisateurs existants
    cursor = conn.execute("SELECT COUNT(*) FROM user")
    nb_users = cursor.fetchone()[0]

    print(f"Utilisateurs existants : {nb_users}")
    print(f"Colonnes a ajouter a 'user' : {[c[0] for c in user_additions] if user_additions else 'aucune'}")
    print(f"Colonnes a ajouter a 'contact' : {[c[0] for c in contact_additions] if contact_additions else 'aucune'}")

    if dry_run:
        print("\n[DRY-RUN] Modifications prevues :")
        for col, typedef in user_additions:
            print(f"  ALTER TABLE user ADD COLUMN {col} {typedef}")
        for col, typedef in contact_additions:
            print(f"  ALTER TABLE contact ADD COLUMN {col} {typedef}")
        if 'role' not in user_cols:
            print(f"  UPDATE user SET role='admin' ({nb_users} utilisateur(s))")
        if 'is_active' not in user_cols:
            print(f"  UPDATE user SET is_active=1 ({nb_users} utilisateur(s))")
        if 'created_at' not in user_cols:
            print(f"  UPDATE user SET created_at=<now> ({nb_users} utilisateur(s))")
        print("\n[DRY-RUN] Aucune modification effectuee.")
        conn.close()
        return True

    # Backup
    backup_path = backup_db(db_path)
    print(f"Backup : {backup_path}")

    try:
        # Ajouter les colonnes a user
        for col, typedef in user_additions:
            conn.execute(f"ALTER TABLE user ADD COLUMN {col} {typedef}")
            print(f"  + user.{col}")

        # Mettre role='admin' pour les utilisateurs existants
        if 'role' not in user_cols:
            conn.execute("UPDATE user SET role = 'admin'")
            print(f"  role='admin' pour {nb_users} utilisateur(s) existant(s)")

        # Mettre is_active=1 pour les utilisateurs existants
        if 'is_active' not in user_cols:
            conn.execute("UPDATE user SET is_active = 1")
            print(f"  is_active=1 pour {nb_users} utilisateur(s) existant(s)")

        # Mettre created_at pour les utilisateurs existants
        if 'created_at' not in user_cols:
            now = datetime.utcnow().isoformat()
            conn.execute("UPDATE user SET created_at = ?", (now,))
            print(f"  created_at={now} pour {nb_users} utilisateur(s) existant(s)")

        # Ajouter les colonnes a contact
        for col, typedef in contact_additions:
            conn.execute(f"ALTER TABLE contact ADD COLUMN {col} {typedef}")
            print(f"  + contact.{col}")

        conn.commit()
        print(f"\nMigration terminee avec succes.")

    except Exception as e:
        conn.rollback()
        print(f"ERREUR lors de la migration : {e}")
        conn.close()
        return False

    conn.close()
    return True


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Migration : gestion multi-utilisateurs')
    parser.add_argument('--db', default=DEFAULT_DB, help=f'Chemin de la base SQLite (defaut: {DEFAULT_DB})')
    parser.add_argument('--dry-run', action='store_true', help='Simulation sans modification')

    args = parser.parse_args()
    success = migrate(args.db, dry_run=args.dry_run)
    sys.exit(0 if success else 1)