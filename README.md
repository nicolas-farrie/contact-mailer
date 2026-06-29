# Contact Mailer

Application web de gestion de contacts et d'envoi d'emails en masse, conçue pour un usage local et souverain (aucune donnée externalisée).

## Fonctionnalités

### Gestion des contacts
- Création, modification, suppression de contacts (avec corbeille — restauration possible)
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
- **Demandes de diffusion** : les contacts peuvent demander la diffusion d'un message via une boîte email
  dédiée ; les utilisateurs relisent et adaptent ces demandes avant envoi (pas de réponse automatique)

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

### Personnalisation par instance
- **Page Paramètres** (admin) : nom de l'application, image de fond du login, opacité du voile
- **PWA / icône bureau mobile** : icône colorée générée dynamiquement avec les initiales de l'instance (`INSTANCE_NAME` + `INSTANCE_COLOR` dans `.env`)
- **`DISPLAY_NAME`** : nom d'affichage UI découplé de l'identifiant technique `INSTANCE_NAME` (navbar + login)
- Manifest PWA dynamique : nom et couleur de l'app adaptés par instance

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
| `tools/migrate_add_softdelete.py` | Migration : ajout champs corbeille (is_deleted, deleted_at, deleted_by_id) (`--dry-run` disponible) |

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

## Versioning des images Docker

Pour les déploiements basés sur l'image Docker (`ghcr.io/nicolas-farrie/contact-mailer`), chaque
instance (un carnet de contacts = un déploiement isolé, ex: une association) doit **pinner un tag
de version explicite** dans son `docker-compose.yml`, plutôt que `:latest` :

```bash
# Sur la machine de dev, après avoir validé une version :
git tag v1.0.0
git push --tags
make push   # construit et pousse ghcr.io/.../contact-mailer:v1.0.0 et :latest
```

```yaml
# docker-compose.yml de chaque instance
services:
  app:
    image: ghcr.io/nicolas-farrie/contact-mailer:v1.0.0   # tag figé, pas :latest
```

Ceci permet à chaque instance d'évoluer indépendamment (une association peut rester sur une
version antérieure tant que la mise à jour n'a pas été testée/voulue pour elle), et impose de
relire `docker-compose.yml`/`.env` à chaque montée de version plutôt que de l'appliquer
automatiquement. La version effectivement déployée est visible dans l'application, dans le
header (à côté du nom "Contact Mailer").

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

## Configuration des intégrations API (BookStack / Seafile)

Ces intégrations sont optionnelles : si les variables ne sont pas définies, les menus correspondants restent masqués.

### BookStack

```env
BOOKSTACK_URL=https://wiki.example.com
BOOKSTACK_TOKEN_ID=...
BOOKSTACK_TOKEN_SECRET=...
```

Le token API se génère dans BookStack : **Profil → API Tokens**.

### Seafile

```env
SEAFILE_URL=https://drive.example.com
SEAFILE_TOKEN=...
```

Le token API se génère via l'API : `curl -d "username=...&password=..." https://drive.example.com/api2/auth-token/`,
ou via un compte admin Seafile (**Avatar → Paramètres → Mes tokens API**, si disponible selon la version).

L'URL configurée est affichée dans le titre des pages BookStack/Seafile, pratique si vous gérez plusieurs instances.

> **⚠️ Attention** : en éditant le `.env`, vérifiez l'absence de caractères invisibles ou parasites en fin de ligne
> (espaces, `>` issus d'un copier-coller depuis un terminal...). Une URL du type `https://drive.example.com   >`
> ne sera ni affichée correctement, ni acceptée par l'API. Vérification rapide :
> ```bash
> grep -n "SEAFILE_URL\|BOOKSTACK_URL" .env | cat -A
> ```
> Une ligne propre se termine par `$` juste après l'URL.

## Demandes de diffusion (boîte IMAP dédiée)

Pour permettre à vos contacts de demander la diffusion d'un message sans mettre en place un système
de type liste de diffusion (réponse automatique à tous), Contact Mailer peut surveiller une boîte
email dédiée par IMAP :

```env
IMAP_HOST=imap.example.com
IMAP_PORT=993
IMAP_USER=demande-diffusion@votre-domaine.com
IMAP_PASSWORD=...
IMAP_FOLDER=INBOX
IMAP_PROCESSED_FOLDER=Traite
# Optionnel : ne traiter que les messages dont le sujet contient cette chaîne
IMAP_SUBJECT_FILTER=
# Optionnel : ne traiter que les messages adressés à cet alias (en-tête To)
IMAP_TO_FILTER=
```

Fonctionnement :
- Un contact écrit à l'adresse dédiée (ex: `demande-diffusion@votre-domaine.com`) pour demander
  l'envoi d'un message à une liste.
- Les messages reçus apparaissent dans **Mailing → Demandes**, accessible à tous les utilisateurs.
- **Utiliser pour un mailing** pré-remplit un nouveau mailing (sujet, corps, pièces jointes) à partir
  de la demande — **à relire et adapter avant envoi** (notamment la liste de destinataires, qui n'est
  jamais pré-sélectionnée).
- **Archiver** marque la demande comme traitée sans créer de mailing.
- Dans les deux cas, le message est déplacé vers le dossier IMAP `IMAP_PROCESSED_FOLDER` (créé
  automatiquement si besoin) : l'état des demandes est géré par les dossiers de la boîte, pas par
  une table en base.
- Aucune dépendance supplémentaire : utilise uniquement `imaplib`/`email` (bibliothèque standard
  Python).
- Avec une adresse dédiée, tous les messages reçus sont considérés comme des demandes. Si la
  boîte est partagée avec d'autres usages (ou pour des tests sur une boîte existante), renseignez
  `IMAP_SUBJECT_FILTER` (ex: `mailing:`) : seuls les messages dont le sujet contient cette chaîne
  seront listés dans Demandes.
- Si la boîte reçoit plusieurs alias (ex: `contact@` et `diffusion@` qui pointent vers la même
  boîte), renseignez `IMAP_TO_FILTER` (ex: `diffusion@votre-domaine.com`) : seuls les messages
  adressés à cet alias seront listés dans Demandes. Combinable avec `IMAP_SUBJECT_FILTER`
  (les deux filtres sont alors cumulatifs : il faut correspondre aux deux).
  La recherche IMAP `TO` porte sur l'en-tête `To:` du message — si votre hébergeur réécrit
  cet en-tête lors de la redirection d'alias (catch-all), vérifiez sur un message de test
  qu'il contient bien l'alias attendu (sinon `IMAP_TO_FILTER` ne matchera jamais et
  aucune demande n'apparaîtra).

## Roadmap

### Fait (v1.1.x)
- [x] PWA manifest dynamique : icône colorée avec initiales par instance (`INSTANCE_NAME`, `INSTANCE_COLOR`)
- [x] `DISPLAY_NAME` : nom d'affichage UI découplé de l'identifiant technique
- [x] Page Paramètres admin (`/settings`) : nom de l'app, image de fond login, opacité voile, sidebar regroupant Seafile/BookStack
- [x] Icône instance dans la navbar et la page de connexion
- [x] Formulaire utilisateur : création depuis fiche contact en tête, email copié comme identifiant
- [x] Fiche contact : métadonnées techniques (UID, Source, Créé/Modifié par) réservées aux admins
- [x] Corbeille contacts : soft-delete avec restauration et purge définitive admin

### À faire
- [ ] Texte d'aide sur le flow mot de passe (formulaire utilisateur)
- [ ] Texte d'aide sur les rôles et leurs droits (page gestion utilisateurs)
- [ ] Refactoring `src/` : regrouper les `.py` dans un sous-répertoire (v1.2.0)

## Licence

Usage privé.
