# Contact Mailer

Application web de gestion de contacts et d'envoi d'emails en masse, conçue pour un usage local et souverain (aucune donnée externalisée).

## Fonctionnalités

### Gestion des contacts
- Création, modification, suppression de contacts
- **UID unique** par contact (compatible vCard : Roundcube, Proton, Thunderbird)
- **Adresse postale** structurée (rue, complément, ville, CP, région, pays)
- **Source** auto-détectée à l'import (Roundcube, Proton, Infomaniak, etc.)
- Recherche, filtrage par liste et par source
- Actions en masse (sélection multiple)
- Emails non uniques : deux contacts peuvent partager la même adresse

### Gestion des listes
- Listes de contacts (relation many-to-many)
- Un contact peut appartenir à plusieurs listes
- Création/suppression de listes, ajout/retrait de contacts

### Import / Export
- **Import vCard** (.vcf) : versions 2.1, 3.0 et 4.0 (via vcard_converter.py)
- **Import TSV / CSV** : détection automatique du séparateur
- **Export TSV** : global ou par liste (avec UID, adresse, source)
- Les listes vCard (catégories) sont automatiquement converties en listes
- Détection de doublons : par UID (priorité), puis email+nom+prénom
- **Migration** : script avec backup automatique et `--dry-run`

### Mailing
- Envoi d'emails personnalisés par liste de contacts
- Variables de personnalisation : `{prenom}`, `{nom}`, `{email}`, `{organisation}`, `{adresse_*}`, `{uid}`, etc.
- Support **texte brut** et **HTML** (éditeur Quill WYSIWYG, HTML par défaut)
- File d'attente avec suivi (envoyé / en attente / erreur)
- **Historique des campagnes** avec réutilisation du message pour un nouvel envoi
- **Prévisualisation** avec navigation entre les contacts de la liste
- **Sauvegarde automatique** du brouillon (localStorage)
- **Copie expéditeur** : une copie de chaque campagne est envoyée au sender
- **Rate-limiting** configurable (emails/minute)
- Envoi via SMTP existant (pas de serveur mail à configurer)

### Désabonnement (RGPD)
- Lien de désabonnement dans chaque email (activable par campagne)
- Header `List-Unsubscribe` (RFC 2369) pour les clients mail compatibles
- Page publique de confirmation avant désabonnement
- Exclusion automatique des contacts désabonnés à l'envoi
- Réabonnement possible par un administrateur
- Badge "Désabonné" visible dans la liste des contacts

### Mot de passe oublié
- Page publique `/forgot-password`
- Notification par email à l'administrateur (pas de tokens)
- Message identique que le compte existe ou non (sécurité)

### Sécurité
- Authentification par login/mot de passe
- **Rôles** : admin (accès complet) et user (pas d'import/export)
- Données stockées localement (SQLite)
- Aucun service externe requis

## Stack technique

- **Backend** : Python 3, Flask, SQLAlchemy
- **Base de données** : SQLite
- **Frontend** : HTML/CSS, JavaScript vanilla
- **Envoi** : SMTP (compatible tout fournisseur)
- **Déploiement** : Gunicorn + Nginx + systemd

## Scripts d'administration (tools/)

| Script | Usage |
|--------|-------|
| `tools/devserver.sh` | Lance le serveur de développement local |
| `tools/setadmin.py` | Créer/modifier le compte admin |
| `tools/resetdb.py` | Réinitialiser la base de données |
| `tools/testsmtp.py` | Tester la connexion SMTP |
| `tools/create_instance.sh` | Créer une nouvelle instance (multi-instance) |
| `tools/migrate_add_uid.py` | Migration : ajout UID, adresse, source (`--dry-run` disponible) |
| `tools/migrate_add_unsubscribe.py` | Migration : ajout champs désabonnement (`--dry-run` disponible) |

## Installation rapide (développement)

```bash
git clone https://github.com/nicolas-farrie/contact-mailer.git
cd contact-mailer
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Éditer .env (SMTP, mot de passe admin)
bash tools/devserver.sh
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
sudo certbot --nginx -d yoursundomain.yourdomain.ext
```

## Déploiement multi-instance

L'architecture multi-instance permet d'héberger plusieurs carnets de contacts isolés sur un même serveur. Chaque carnet = une instance Flask séparée avec sa propre base SQLite, son propre `.env`, et son propre service systemd.

```
listes.aubaygues.fr/          → landing page (choix du carnet)
listes.aubaygues.fr/asso1/    → instance asso1 (gunicorn :5001)
listes.aubaygues.fr/asso2/    → instance asso2 (gunicorn :5002)
```

### Créer une instance

```bash
sudo bash tools/create_instance.sh --name asso1 --port 5001
sudo nano /opt/contact-mailer-instances/asso1/.env   # Configurer SMTP
sudo systemctl daemon-reload
sudo systemctl enable --now contact-mailer-asso1
sudo nginx -t && sudo systemctl reload nginx
```

### Configuration nginx

Déployer `deploy/nginx-multi.conf` dans `/etc/nginx/sites-available/` et créer le lien symbolique. Les blocs location par instance sont inclus automatiquement depuis `/etc/nginx/contact-mailer-instances/`.

### Fichiers de déploiement

| Fichier | Description |
|---------|-------------|
| `deploy/nginx-multi.conf` | Config serveur nginx (landing + includes) |
| `deploy/instance.service.template` | Template service systemd par instance |
| `deploy/instance.nginx.template` | Template bloc location nginx par instance |
| `deploy/landing/index.html` | Landing page statique (choix du carnet) |

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
BASE_URL=https://votre-domaine.com
```

| Port | SMTP_USE_TLS | Protocole |
|------|-------------|-----------|
| 587  | true        | STARTTLS  |
| 465  | false       | SSL/TLS   |

## Licence

Usage privé.
