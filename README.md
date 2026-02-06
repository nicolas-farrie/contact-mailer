# Contact Mailer

Application web de gestion de contacts et d'envoi d'emails en masse, conçue pour un usage local et souverain (aucune donnée externalisée).

## Fonctionnalités

### Gestion des contacts
- Création, modification, suppression de contacts
- Recherche et filtrage
- Actions en masse (sélection multiple)

### Gestion des listes
- Listes de contacts (relation many-to-many)
- Un contact peut appartenir à plusieurs listes
- Création/suppression de listes, ajout/retrait de contacts

### Import / Export
- **Import vCard** (.vcf) : versions 2.1, 3.0 et 4.0 (via [vcard_converter](https://github.com/nicolas-farrie/contact-mailer))
- **Import TSV / CSV** : détection automatique du séparateur
- **Export TSV** : global ou par liste
- Les catégories vCard sont automatiquement converties en listes
- Mise à jour des contacts existants à l'import (détection par email)

### Mailing
- Envoi d'emails personnalisés par liste de contacts
- Variables de personnalisation : `{prenom}`, `{nom}`, `{email}`, `{organisation}`
- Support **texte brut** et **HTML**
- File d'attente avec suivi (envoyé / en attente / erreur)
- **Rate-limiting** configurable (emails/minute)
- Envoi via SMTP existant (pas de serveur mail à configurer)

### Sécurité
- Authentification par login/mot de passe
- Données stockées localement (SQLite)
- Aucun service externe requis

## Stack technique

- **Backend** : Python 3, Flask, SQLAlchemy
- **Base de données** : SQLite
- **Frontend** : HTML/CSS, JavaScript vanilla
- **Envoi** : SMTP (compatible tout fournisseur)
- **Déploiement** : Gunicorn + Nginx + systemd

## Installation rapide (développement)

```bash
git clone https://github.com/nicolas-farrie/contact-mailer.git
cd contact-mailer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditer .env (SMTP, mot de passe admin)
python app.py
```

Accès : http://localhost:5000 (admin / changeme)

## Déploiement (Ubuntu Server 24.04)

```bash
sudo bash deploy/install.sh
sudo nano /opt/contact-mailer/.env   # Configurer SMTP et admin
sudo systemctl restart contact-mailer
```

Puis pour HTTPS :
```bash
sudo certbot --nginx -d groupes.aubaygues.fr
```

## Configuration SMTP

Éditer le fichier `.env` :

```env
SMTP_HOST=mail.example.com
SMTP_PORT=465
SMTP_USER=user@example.com
SMTP_PASSWORD=motdepasse
SMTP_SENDER_EMAIL=user@example.com
SMTP_SENDER_NAME=Mon Organisation
SMTP_USE_TLS=false
MAIL_RATE_PER_MINUTE=20
```

| Port | SMTP_USE_TLS | Protocole |
|------|-------------|-----------|
| 587  | true        | STARTTLS  |
| 465  | false       | SSL/TLS   |

## Licence

Usage privé.
