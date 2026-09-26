# Contact Mailer - TODO
# le [ ] vide indique non fait ; le [x] fait ; le [~] partiellement fait ; le [?] pas sûr qu'il faille le faire (à rediscuter)
# - [ ][ ] - sous point
## État au 25/09/2026 (audit TODO ↔ code)

Le fichier avait trois semaines de retard : **30 items ouverts étaient déjà faits** et ont été
cochés ce jour (EPIC Sélection S2→S5 au complet, envoi asynchrone, recherche avancée, segments,
champs de formulaire éditables et sécurité du lien public, audit, WAL, journalisation, modèles de
mailing, page À propos…). Ce qui suit est ce qui reste VRAIMENT, par ordre d'urgence.

**Risques d'exploitation** — à traiter en premier :
1. ~~Timeout IMAP~~ → **fait le 25/09** (`Config.IMAP_TIMEOUT`, 14 connexions réseau couvertes).
2. ~~Protection CSRF~~ → **faite le 25/09** (Flask-WTF, 80 formulaires + les appels fetch).
3. **`update.sh` hors git avec prune inconditionnel** (dépôt `contact-mailer-deploy`) : il détruit
   l'image de rollback. Invisible tant que claude-serveur déploie à la main.
4. **Fork-safety** : `--preload` sans `dispose()` au post-fork.
5. **Scan des bounces resté manuel** — le mécanisme existe, rien ne le déclenche périodiquement.
6. **RGPD — suppression d'un utilisateur** : hard delete laissant des références orphelines ;
   sans effet sur SQLite, bloquant le jour d'un portage Postgres.

**En attente d'un tiers** : quotas mutualisés entre instances (réponse LWS).

**Analysé, chiffré, non codé** : plages alphabétiques dans les filtres (~½ journée).

**Petits restes fonctionnels** : landing après connexion (on arrive sur Contacts, Listes voulu),
pied de mail « nom de la liste + inscrits », brouillon enregistrable sans liste cochée, avertir du
doublon catégorie/activité, fusion de deux listes, traçabilité de l'expéditeur d'une demande.

**Documentation utilisateur** : 3 guides publiés (démarrage, intégrations, segments) ; manquent
Mailing, Contacts, Formulaires.

## Fait
- [x] Gestion contacts (CRUD)
- [x] Gestion listes (many-to-many)
- [x] Actions en masse (ajout/retrait liste, suppression)
- [x] Import TSV/CSV
- [x] Import vCard (via vcard_converter.py)
- [x] Export TSV (global et par liste)
- [x] Mailing avec personnalisation ({prenom}, {nom}, etc.)
- [x] File d'attente + suivi (campagnes)
- [x] Rate-limiting configurable
- [x] Headers email corrects (Date, Message-ID, Content-Language)
- [x] Support HTML dans les mails
- [x] Mise à jour contacts existants à l'import (remplacement listes)
- [x] Authentification admin simple
- [x] Configuration Nginx (reverse proxy Dell-9010 → MSI-01)
- [x] Sécurisation : SECRET_KEY, mot de passe admin, HTTPS (Let's Encrypt)
- [x] Service systemd pour l'exécution en production (gunicorn)
- [x] Scripts d'administration (tools/ : devderver, setadmin, resetdb, testsmtp)
- [x] UID indépendant de l'email (String 255, compatible Roundcube/Proton)
- [x] Adresse postale structurée (rue, complément, ville, CP, région, pays)
- [x] Champ source (provenance auto-détectée : Roundcube, Proton, Infomaniak, etc.)
- [x] Import : déduplication UID puis email+nom+prénom, emails non uniques
- [x] Export TSV enrichi (UID, adresse, source)
- [x] Filtre par source dans la vue contacts
- [x] Migration automatique avec backup (tools/migrate_add_uid.py)
- [x] Gestion des désabonnements RGPD : lien dans les emails, page publique avec confirmation, exclusion à l'envoi, réabonnement admin
- [x] Copie automatique de la campagne à l'expéditeur (sujet enrichi, récapitulatif résultats, pièces jointes)
- [x] Import/export réservés aux administrateurs (@admin_required)
- [x] Interface améliorée : layout pleine largeur (contacts, mailing), éditeur HTML par défaut
- [x] Preview mailing : navigation entre contacts (boutons prev/next), toggle afficher/masquer
- [x] Sauvegarde automatique du brouillon mailing (localStorage)
- [x] Interface responsive mobile : hamburger nav, cards contacts, numéros en clic-to-call
- [x] Lien utilisateur ↔ fiche contact (contact_id FK, select admin, info-box profil)
- [x] Retour à la liste filtrée après édition d'un contact 
- [x] Gestion multi-utilisateurs : CRUD users, rôles admin/user, qui a fait quoi
- [x] Déploiement multi-instance : middleware ReverseProxied, templates systemd/nginx, script create_instance.sh, landing page
- [x] Mot de passe oublié : notification admin par email (sans tokens)
- [x] Intégration API BookStack : sync rôles, push contacts avec rôle, invitation optionnelle, langue fr par défaut
- [x] Problème de cohérence entre les dénominations de champ, dans la base, à l'import, et en affichage (ex listes | catégories | groups)
- [x] Liste des messages déjà envoyés, réutilisation pour nouvel envoi
- [x] user_edit : erreur 500 sur chemins d'erreur (contacts non passé au template)
- [x] Bulk actions : "Retirer de la liste" corrigé (formulaires imbriqués), retour au filtre courant, confirmation avant action
- [x] Historique mailing : réutilisation du texte et de la liste corrigée
- [x] Bulk actions disponibles sur mobile : checkboxes sur les cards, barre toggle "Actions ▾"
- [x] Code couleur boutons : bleu création, orange modification, vert foncé action/filtre, rouge suppression
- [x] Filtre contacts : réorganisation (liste → source → recherche → bouton), source réservée aux admins
- [x] Favicon SVG (onglet navigateur + icône mobile)
- [x] Sélection des contacts à l'envoi d'un mailing (page de confirmation avec cases à cocher)
- [x] Réutilisation historique mailing : chargement complet (sujet, corps, liste) via campaign_id
- [x] Intégration API Seafile : push contacts → users, listes → groupes, mots de passe temporaires en DB
- [x] Seafile : envoi mailing d'invitation avec variables {seafile_password}, {seafile_url}, message personnalisé
- [x] Seafile : régénération mots de passe avec sélection de contacts par liste
- [x] Éditeur HTML : remplacement Quill par TinyMCE (self-hosted jsDelivr, support listes imbriquées)
- [x] Preview mailing : rendu HTML via iframe srcdoc (isolation CSS, listes correctement rendues)
- [x] Pièces jointes : limite 5 Mo (MAX_CONTENT_LENGTH Flask + client_max_body_size nginx)
- [x] Parser mailing : conditions {champ:if_true:if_false} et {champ==val:if_true:if_false}
- [x] Dockerisation : Dockerfile, docker-compose, Makefile, registry ghcr.io, repo contact-mailer-deploy
- [x] Tri colonnes cliquable (contacts, utilisateurs, historique mailing)
- [x] Suppression campagne dans l'historique (admin uniquement)
- [x] Navigation mailing unifiée (historique/file/nouveau sur les 3 pages), entrée par l'historique
- [x] Édition utilisateur : remplissage auto nom/prénom/email depuis la fiche contact liée (avec confirmation si déjà rempli)
- [x] Pages BookStack/Seafile : affichage de l'instance connectée dans le titre
- [x] README : documentation configuration BookStack/Seafile + avertissement caractères parasites .env
- [x] Demandes de diffusion : boîte IMAP dédiée, page "Demandes" (4e bouton nav mailing), pré-remplissage mailing depuis une demande, archivage (dossier IMAP "Traité")
- [x] PWA manifest dynamique : icône colorée avec initiales par instance (INSTANCE_NAME + INSTANCE_COLOR)
- [x] DISPLAY_NAME : nom d'affichage UI découplé de l'identifiant technique
- [x] Page Paramètres admin (/settings) : nom de l'app, image de fond login, opacité voile, sidebar Seafile/BookStack
- [x] Formulaire utilisateur : création depuis fiche contact en tête, email copié comme identifiant
- [x] Fiche contact : métadonnées techniques (UID, Source, Créé/Modifié par) réservées aux admins
- [x] Corbeille contacts : soft-delete (is_deleted + deleted_at + deleted_by), restauration et purge admin dans Paramètres
- [x] Formulaires de préférences : lien unique par contact (token + uid), cases liées aux Listes, auto-apply, expires_at, page publique sans login
- [x] Gestion des bounces SMTP : Return-Path configurable, scan IMAP dédié, marquage has_bounced + badge, réinitialisation admin

### Fait le 6 juillet 2026 (branche fix/formulaires, sur restructure)
- [x] Restructuration code : app.py monolithe (2289 l.) découpé en 9 blueprints par domaine (contacts, listes, formulaires, mailing, users, imports, api_integrations, settings, public) + extensions.py/helpers.py + factory create_app() — entrypoint `app:app` et `from app import app,db,init_db` inchangés
- [x] Fix mailing.process : import pathlib.Path manquant (la copie récap à l'expéditeur échouait quand la campagne avait des pièces jointes)
- [x] Formulaire création : champ "date de clôture" affiché + enregistré (était masqué et non lu → validité illimitée forcée)
- [x] Formulaire : archivage soft/réversible (colonne is_archived + migration), autorisé seulement si déjà clos (date de clôture passée), section "Archivés" dépliable, réponses conservées
- [x] Formulaire : suppression réservée admin, uniquement depuis les archivés, confirmation forte (les users archivent, les admins purgent)
- [x] Formulaire : colonne "Clôture" dans la liste (date + illimité/clos) ; aide déconseillant les formulaires illimités
- [x] Formulaire détail : "Copier le lien" → retour "Copié ✓" non-bloquant (plus d'alert)
- [x] Mailing : URLs collées en texte brut rendues cliquables à l'envoi (auto-linkify, {uid} résolu par contact)
- [x] Mailing : liens désactivés dans l'aperçu (évite qu'en prévisualisant on modifie de vraies données via un formulaire live)

## Correction Bug ou pb interface - Prioritaire
- [ ] **Landing page : après connexion, on arrive sur Contacts au lieu de Listes** *(10/09/2026)*.
      Les listes sont le point d'entrée naturel du travail (on part d'une liste pour écrire, pour
      importer, pour filtrer) ; ouvrir sur la totalité des contacts oblige à un détour à chaque
      session. À vérifier : la route `/` redirige aujourd'hui vers `contacts.index`.

- [x] **🔴 Mailing : séquence d'envoi phase 3 → phase 4 — CORRIGÉ (08-04, Tier 0)**. La confirmation de l'étape Destinataires **déclenche réellement l'envoi** : `add_to_queue` met en file **puis** `_run_send()` (envoi immédiat) → on arrive en phase Envoi sur un **état résultat**. `process()` devient « Reprendre l'envoi » (file d'attente, cas interrompu/erreurs). Modale unique « Envoyer maintenant » + overlay. Prépare l'asynchrone (confirmer = file + armer le déclencheur). *(Fini le « resté en file, jamais parti ».)*

## A faire - Prioritaire

### 🚨 URGENT — Délivrabilité e-mail : anti-bounce, validation & IP dédiée (plan cadré 2026-08-18)
**Source : conversation LWS, CR dans `doc-travail/vrai-prompt-fiable.md` #30.** À traiter **après** la fin de la session d'hier (déploiement Sélection courante v2.2.3 + PJ demandes + demandes traitées).

**Ce que LWS nous a appris (offre mutualisée asso34.fr) :**
- Limites dures : **240 envois/heure** (compteur horaire, pas à la minute) · **2500/jour**. Envoi **par lot sans reconnexion** (= valide notre Fix #1 connexion unique).
- **VPS / IP dédiée** chez LWS → limites supprimées **+** adresse bounce active **+** logs d'envoi accessibles.
- SPF/DKIM/DMARC asso34.fr : **OK**, rien à toucher (écarte l'auth comme cause de rejet).
- Logs de rejet riches dans leur UI (1000 derniers) mais **PAS d'API** → pas de bounce programmatique via leurs logs.
- **Reco #1 de LWS** : « rien de pire que de représenter plusieurs fois des mails en erreur » → suppression stricte + **valider l'adresse à la saisie/màj** (test rapide, « 100% efficace » en base opt-in).

**Stratégie retenue (3 couches) :**
1. **Suppression** (ne jamais remailer une adresse en erreur) — gratuit, illimité, prioritaire.
2. **Prévention à la saisie** — format+MX partout (gratuit) ; API temps-réel (ping SMTP + jetables) **en option, aux points à faible débit seulement**.
3. **Plafonds** recalés aux vraies limites.

**Constats de code (vérifiés le 2026-08-18) :**
- ⚠️ **L'envoi n'exclut PAS `has_bounced`** : `active_contacts` exclut seulement `is_deleted`, `_recipients` seulement `is_unsubscribed`. Un contact en erreur **est remailé** — exactement ce que LWS proscrit. (Le seul usage de `has_bounced`, `mailing.py:207`, ne sert qu'à une **stat d'affichage** dans l'historique.)
- ✅ **La boucle de bounce est déjà à 100% construite** : `bounce_scanner.py` = vrai parseur DSN (RFC 3464 `Final-Recipient`, header `X-Failed-Recipients`, fallback regex codes 550-554 + mots-clés FR/EN ; détection `MAILER-DAEMON`/sujets/`multipart/report`) ; lit **n'importe quelle boîte IMAP** via `BOUNCE_IMAP_*` ; la route `contacts.scan_bounces` marque `has_bounced=True` + `bounced_at` et déplace le DSN en « Traité ». Config `BOUNCE_IMAP_*` + `BOUNCE_RETURN_PATH` déjà en place.
- ⚠️ **Aucune validation de format e-mail** à la saisie aujourd'hui (fiche/formulaire/import).

**Insight clé (corrige la crainte « has_bounced restera toujours false ») :** sans IP dédiée, les NDR reviennent au **From = boîte d'expédition asso34.fr** (accessible en IMAP). En pointant `BOUNCE_IMAP_*` sur cette boîte, la boucle fonctionne **sur mutualisée, sans VPS**. Cohérent avec le fix 553 (bounce_enabled OFF = pas de Return-Path forcé → NDR au From). Le VPS devient un **upgrade** (boîte bounce dédiée non mêlée aux réponses humaines + logs + pas de plafonds), pas un prérequis.

**Design `email_verified` (tri-état) — validé avec correction :**
- `None` = jamais testé (cas import) · `True` = API OK · `False` = API dit invalide (exclu).
- **Correction cruciale : ne JAMAIS conditionner l'envoi en masse à l'API** (100/mois → un import 3500 explose le quota qu'on vérifie à l'import OU « au 1er usage »). Le **gate d'envoi = gratuit** (format+MX + `not has_bounced` + `not unsubscribed`). L'API = **bonus qualité** aux points de saisie (fiche + formulaire public), jamais un blocage de campagne. Réponse à « non-vérifiées > quota » : les `None` partent sur confiance format+MX ; l'API ne les atteint simplement pas ce mois-ci. → béquille assumée ; la vraie réponse = la boucle bounce (gratuite, illimitée, **auto-corrective**).

**PLAN D'EXÉCUTION (dans l'ordre) :**
- [x] **1a. Exclure `has_bounced` de l'envoi** (consommateur de la boucle) — modifier `_recipients` (+ cohérence `active_contacts`/`joignables`). Petit, sûr.
- [x] **1b. Recaler les plafonds** aux vraies limites avec marge : `MAIL_MAX_PER_HOUR` 100→~220, `MAIL_MAX_PER_DAY` 300→~2400 (defaults code surchargeables `.env`). `MAIL_RATE_PER_MINUTE` : lissage modeste (LWS compte à l'heure).
- [ ] **2. TEST EMPIRIQUE de la boucle sur lfll** (tranche la question « sommes-nous aveugles ? ») : `.env` `BOUNCE_IMAP_*` = boîte d'expédition ; envoyer à une adresse invalide (`nexistepas@asso34.fr`) ; attendre le NDR ; « Scanner les bounces » ; vérifier `has_bounced=True`. → NDR arrive = boucle OK sur mutualisée / VPS = confort ; NDR n'arrive pas = argument chiffré pour le VPS.
- [ ] **3. Validation format+MX à la saisie** (prévention amont) : fiche contact + formulaire public + import (rejet du garbage évident, gratuit, illimité).
- [ ] **4. `email_verified` tri-état + API togglable** (clé `.env`) aux points de saisie faible débit uniquement. Choisir le fournisseur (AbstractAPI 100/mois gratuit = dépannage ; palier payant si la prévention devient centrale).
- [ ] **5. Scan bounce périodique** (au lieu du bouton manuel) : cron/APScheduler — mutualise avec le scan des demandes de diffusion (cf. section « Notification des demandes »).
- [ ] **6. DÉCISION VPS / IP dédiée** — sur la base du test #2. **Chiffrage à produire (doc dédiée) :**
  - *Périmètre A — mail seul (app reste sur home-servers)* : provisionner IP dédiée/VPS mail ; DNS SPF+DKIM pour la nouvelle IP ; `.env` (SMTP + activer `BOUNCE_IMAP_*`) ; finir/valider câblage `bounce_scanner`. **Coût logiciel faible** (code prêt), essentiel = deliverability + tests (~1 session).
  - *Périmètre B — app entière sur VPS* : Docker + nginx/TLS + migrer volumes (pattern rodé aubaygues) + repoint DNS + décommissionner. Plus lourd mais maîtrisé. **Bonus : règle la fiabilité (fini les incidents UPS/coupure).**
  - Combinables. Le **coût de migration doit être évalué et intégré au choix** (demande explicite Nicolas).
- [note] Solution API = **béquille** assumée, à revoir selon la taille des imports. La cible durable = boucle bounce + IP dédiée.

### 📥 Import v2 — MVP-1 LIVRÉ (2026-08-05/06), MVP-2 à faire (urgence sénatoriales)
Détail complet : `doc-travail/2026-08-06-import-v2-etat-et-suite.md`. Branche `design/claude-design-v2`, non déployé.
- [x] Parseur **openpyxl (.xlsx) + csv/tsv**, décodage utf-8→cp1252 (Excel FR) — `1a45a66`
- [x] Écran **mapping colonnes↔champs** registre-driven + auto-suggestion ; **sans email accepté** ; export **modèle CSV**
- [x] **Tester l'import (à blanc)** + compteurs ; **Nouvelle liste** à la volée ; redirection vers la liste peuplée — `d76c20d`
- [x] **Dédoublonnage = Nom+Prénom** (email = affinage optionnel) → fichiers sans email ne doublonnent plus (validé sur *maires Hérault* : 0 créé / 341 màj) — `42d7abd`
- [x] Listes **archivées exclues** des choix de liste (import **et** page contact) ; `_apply_listes` préserve les adhésions archivées — `e11eb46`+`42d7abd`
- [x] **MVP-2 — créer un champ perso à l'import** — `b79ff90`. Le socle `CustomFieldDefinition` existait déjà (modèle + table + 14 champs + CRUD Paramètres + rendu fiche). Ajouté : option « ➕ Créer un champ personnalisé… » sur l'écran mapping (libellé + type), création idempotente à l'import. `slugify_key` promu dans `helpers` (partagé settings↔import).
- [x] **MVP-2 — coercition par type** — `bdb9a64`. checkbox (TRUE/oui/1/x → coché ; FALSE/non/0/vide → décoché/absent — **corrige un bug** : « FALSE » truthy en Jinja affichait « Oui »), date → ISO (gère datetime openpyxl + FR), vide → None.
- [~] **MVP-2 — « tester l'import » avec ERREURS par ligne** (demande Nicolas) : **REPORTÉ** (2026-08-06) — sous-chantier design-lourd (taxonomie erreurs + UI par ligne + ré-export) ; rien ne bloque aujourd'hui (coercition tolérante). À reprendre si gros fichiers « sales ».
- [x] **MVP-2 — mappings sauvegardés** — `d86aaa9`. Modèle `ImportMapping` + migration ledger. Écran mapping : « 💾 Enregistrer ce mapping » (nommé) ; **auto-application** du meilleur mapping enregistré (≥2 colonnes reconnues, par nom, modifiable) à l'upload + liste déroulante « Appliquer » manuel. _Reste possible (non demandé) : écran de gestion/suppression des mappings enregistrés (aujourd'hui : écrasement par ré-enregistrement du même nom)._
- [x] **MVP-2 — segment « à compléter »** — `f943318`. Filtre Contacts `?completude=` : « À compléter » (email OU tél manquant) / « Sans e-mail » / « Sans téléphone ». Amorce l'EPIC Sélection & Segments.
- [ ] MVP-2 — peaufinages import : options d'un champ `select` créé à l'import (naît sans options) ; effet de bord « prévisualiser crée déjà le champ » (à reconfirmer).
- [ ] Brief CLD « mapping sexy » (drag-drop) après validation fonctionnelle.
- [note] Base de dev : doublons possibles créés pendant les tests d'aujourd'hui (avant le fix dédoublonnage) → prévoir au besoin un petit script de dédoublonnage par (nom, prénom).

### Formulaires — 2 gros sujets liés (analyse cadrée le 6/07, à traiter ensemble, sécurité intégrée dès la conception)
- [x] Champs de la base éditables dans le formulaire (self-service auto-correction)
- [ ][ ] Liste blanche de champs éditables par formulaire (comme la sélection des listes → table type PreferenceFormField ou colonne JSON)
- [ ][ ] Page publique : pré-remplissage des valeurs, édition, update du contact ; email/uid exclus par défaut (identité + dedup import) ; traçabilité "modifié par le contact"
- [x] Sécuriser l'accès quand des champs sont exposés (le lien est une "capability URL" : token 128 bits + expiry, HTTPS ; risque = fuite du lien)
- [ ][ ] Option retenue à décider : (préféré) proposition→validation admin — supprime la surface d'injection ; ou OTP e-mail ; ou confirmer un champ connu ; ou SMS OTP (option forte, mais coût provider + numéros mobiles peu fiables)
- [~] ⚠️ Auth ≠ sanitisation : échapper/sanitiser les champs contact partout où ils ressortent NON échappés :
  - [x] **export CSV/TSV + XLSX (formula injection Excel)** — `b14719d` : `_formula_guard` (préfixe espace, round-trip préservé). Corrige aussi l'affichage des tél. « +33… ».
  - [x] **export vCard** — VÉRIFIÉ sûr (vobject échappe `\n \; \,` à la sérialisation), rien à faire.
  - [ ] **mailer replace_vars (HTML des mails)** — RESTE : échapper les variables de fusion injectées dans le HTML des emails (risque réel faible car les clients mail sanitisent, mais bonne pratique). À traiter avec le chantier Formulaires (champs éditables).
- [ ][ ] Paramètre admin : durée maximale de validité (conseil : illimité/très long interdit)
- [ ] Formulaire public : mode "aperçu sans enregistrement" (preview no-data) — reporté en version avancée
- [?] Import interactif : page de revue des doublons avec choix par contact (ignorer/remplacer listes/fusionner listes) + option "pour tous"
- [?] Support templates .eml (brouillons Thunderbird) - format standard RFC 5322

### Notification des demandes de diffusion (important)
- [ ] À la réception d'une **demande de diffusion** (submission IMAP → `mailing.submissions`), envoyer un **email type de notification à TOUS les utilisateurs** reprenant le **sujet** et l'**expéditeur** de la demande — pour que la modération sache qu'une demande est en attente sans surveiller l'interface.
  - [ ][ ] Déclencheur : à l'enregistrement d'une nouvelle demande (une seule notif par demande, éviter les doublons au re-scan IMAP).
  - [ ][ ] Destinataires = tous les utilisateurs actifs (adresses email du modèle `User`) ; contenu = sujet + expéditeur + lien vers l'écran « Demandes de diffusion ».
  - [ ][ ] Gabarit d'email dédié (réutiliser `mailer`) ; envisager un flag admin pour (dés)activer la notification.
  - [ ][ ] **Dépendance** : aucun déclencheur automatique aujourd'hui (la boîte `diff-<instance>` n'est lue que sur ouverture de `GET /mailing/submissions`). Il faut donc **introduire un scan périodique** (cron / systemd timer / APScheduler) qui lit la boîte en fond — c'est lui qui déclenche la notif. Ce scan **peut coexister (en doublon) avec le rafraîchissement à l'ouverture de la page** : les deux chemins lisent la même boîte, donc l'anti-doublon « déjà notifié » (flag IMAP / sous-dossier / table `Message-ID`) protège les deux. À l'occasion, ce scan pourrait aussi câbler `count_pending()` (défini mais inutilisé) pour un badge sur la sidebar.
  - [ ] **DÉCISION (2026-08-25, à faire — demande user, instances actives lfll + adreic34)** : moteur retenu = **B. systemd timer / cron hôte** déclenchant une **commande de scan idempotente** (`docker compose run --rm app python -m scan_submissions` ou équivalent). Rationale : une seule exécution garantie (pas de souci multi-workers gunicorn `--preload`/2 workers de l'option APScheduler in-process), isolé, colle à la topologie (claude-prod gère l'hôte). Le timer se pose **par instance côté hôte** (lfll + adreic34 sur contabo01) — donc **pas dans l'image**, l'image ne fournit que la commande.
    - Anti-doublon = **table locale `NotifiedSubmission(message_id, notified_at)`** (le `Message-ID` du mail = identifiant stable/unique) → partagée par le scan périodique ET le refresh à l'ouverture de page. Migration safe.
    - Envoi : email aux `User` actifs **avec email renseigné** (sujet + expéditeur de la demande + lien `/mailing/submissions`), gabarit dédié via `mailer`, **flag admin on/off**.
    - Effort ~1 session côté app + pose du timer côté hôte par claude-prod. Recouvre le point 5 de l'EPIC délivrabilité (scan bounce périodique) — même mécanique de timer, à mutualiser.

### 🔴 Reply-To par mailing (adresse de réponse ≠ boîte d'envoi) — À FAIRE (2026-08-26, demande user)
- [ ] Permettre qu'une réponse à un mailing arrive sur une **autre adresse** que la boîte d'envoi (cas réel : courrier aux maires envoyé depuis `...@asso34.fr`, mais réponses souhaitées chez la **tête de liste**). = en-tête **`Reply-To`**.
  - [ ][ ] **Ne PAS toucher au `From`** (doit rester le domaine authentifié `@asso34.fr` — SPF/DKIM/DMARC alignés, validés par LWS). Seul `Reply-To` change. **Incidence spam : nulle/négligeable** (usage standard ; `Reply-To` n'entre pas dans SPF/DKIM/DMARC). Micro-précaution : valider que l'adresse est bien formée.
  - [ ][ ] **État code** : AUCUN `Reply-To` aujourd'hui (`mailer.py` ~l.520 pose From/To/Date/Message-ID/Return-Path, pas Reply-To). À ajouter : 1 ligne header `msg['Reply-To']` si défini.
  - [ ][ ] **Portée retenue = PAR CAMPAGNE** (la tête de liste change selon l'envoi) : champ « Répondre à (facultatif) » dans le compositeur → colonne `MailCampaign.reply_to` (migration safe) → injecté à l'envoi. Optionnel plus tard : un **défaut** configurable (Paramètres/profil) pré-remplissant le champ.
  - [ ][ ] Effort ~½ session (migration `reply_to` + champ form + 1 ligne mailer + porter dans le round-trip compose→confirm→queue comme `use_selection`).

### 📋 Retours test beta.2 (prompt #32, 2026-08-25) — filtres avancés OK, reste ces points
Ordre d'attaque convenu (26/08) : Reply-To (section dédiée plus haut) → bugs rapides #3/#2 → daemon de notif (section « Notification des demandes ») → backup Paramètres. Responsive = plus tard.
- [ ] **#3 (bug rapide) — « Vider le brouillon » n'efface pas** : `clearDraft()` (mailing.html) fait `removeItem(draft)+reload`, mais le reload **ré-applique le préremplissage serveur** si l'URL porte `?from_submission=` / `?from_campaign=` → le form se re-remplit. Fix probable : rediriger vers `/mailing` **propre** (sans params) au lieu de `location.reload()`. ~10 min. À confirmer : le cas était-il une demande/réutilisation ou un mailing vierge ?
- [ ] **#2 (bug rapide) — import xlsx : 1022 colonnes affichées (même vides)** : `_read_xlsx` (imports.py) lit toute la dimension de la feuille + invente `colonne N` pour les vides. Fix : ne garder que les colonnes à **en-tête non vide** (tronquer les vides en fin). Rapide.
- [x] **#1 — Sauvegarde de la base dans Paramètres** : bouton snapshot/télécharger la base **avant un import risqué** (surtout création de champs perso). Garde-fou utilisateur (≠ backups de déploiement de claude-prod). ~½–1 session.
  - [ ] **1a — Auto-backup AVANT chaque import** (le plus important) : copie `data/contacts.db` → `data/backups/pre-import-<ts>.db` juste avant d'appliquer un import. Rend l'import réversible (irréversibilité = le vrai risque, pas SQLite). Prioritaire.
- [x] **Robustesse SQLite — activer le mode WAL** (`PRAGMA journal_mode=WAL`) : améliore la concurrence (lecteurs ne bloquent plus l'écrivain ; utile pendant un long import). ATOMICITÉ/ACID **préservées** (WAL est plus robuste, pas moins). NB : WAL ajoute des fichiers `-wal`/`-shm` à côté de `contacts.db` → **la stratégie de backup doit checkpoint ou copier ces fichiers aussi** (sinon `cp contacts.db` seul rate les données non encore checkpointées). → à faire AVEC #1/1a (ils vont ensemble), PAS juste avant un import (changer une chose à la fois). Réglage niveau base (persistant dans l'en-tête du fichier), **pas une colonne/migration**.
- [ ] **#4 — Responsive des listes (REPOUSSÉ, non bloquant)** : sur demi-écran/mobile, icônes/boutons d'action peu accessibles. Chantier CSS transverse (tableaux → cartes/scroll sur petit écran) → **candidat CLD** (parti pris design).
- [ ] **#5 — Recherche mobile peu visible** : à préciser (repro user à venir) ; probablement lié à #4.
- [note] Autres remontées #32 déjà couvertes ailleurs : Reply-To (section dédiée) ; daemon de notif (section « Notification des demandes de diffusion »).

### 🔐 Logs & Journal d'audit (analyse 2026-08-28) — Tier 1 EN COURS, Tier 2 à faire
Deux tiroirs distincts : **Tier 1 = logs système** (dev/ops, stdout→docker) ; **Tier 2 = journal d'audit** (« qui a fait quoi » sur les données, en base + UI Admin). Principe directeur : tracer **données perso + sécurité/accès** (redevabilité RGPD), **JAMAIS le comportement** (navigation, recherches, fiches vues = flicage, exclu).

**Tier 1 — logs système** (⏳ en cours 28/08) :
- [x] `logging.basicConfig` (niveau `LOG_LEVEL` env, défaut INFO, format horodaté) dans `app.py` — aujourd'hui aucune config → INFO avalé, pas de timestamp.
- [x] gunicorn `--capture-output --log-level info` (garder `--access-logfile -`).
- [x] Rotation Docker (compose `logging: json-file, max-size 10m, max-file 5`) — **par instance côté hôte (claude-prod)** : les compose prod sont propres à chaque instance.

**Tier 2 — journal d'audit** (à faire ; **login = URGENT, contexte campagne électorale**) :
- [x] Table `AuditLog(id, ts, user_id, username_snapshot, action, target_type, target_id, details_json, ip?)` — append-only, snapshot du username (survit à la suppression), rétention BORNÉE (purge auto configurable ~12 mois : le journal est lui-même de la donnée perso), IP optionnelle/désactivable.
- [x] Helper `audit(action, target=…, **details)` + branchement des points clés.
- [ ] **Événements pertinents** (cadre non-flicage) :
  - **A. Accès/sécurité** : connexion **réussie** (qui/quand), connexion **ÉCHOUÉE** (identifiant tenté) ← **PRIORITÉ (campagne électorale)** ; changement de mot de passe. *(jamais le mot de passe)*
  - **B. Comptes & droits** : user créé/modifié/désactivé/supprimé ; changement de rôle et de `is_moderator`.
  - **C. Données perso (cœur RGPD)** : **export de contacts** (qui/combien/format — vecteur d'exfiltration, log le plus important) ; import (nb créés/màj) ; suppression en masse / purge définitive ; consentement en masse (désab/réab groupé).
  - **D. Diffusion** : campagne envoyée (qui/listes/nb) — complète `ContactSend`.
  - **E. Config sensible** : SMTP/bounce, création/suppression de champ perso (change le schéma).
  - **NE PAS logger** : consultation de fiche, recherches, navigation, temps passé (flicage, exclu).
- [ ] **Déjà en place à réutiliser** : `Contact.created_by_id/updated_by_id/deleted_by_id/deleted_at` (paternité par enregistrement), `ContactSend` (journal d'envoi). L'audit comble les trous (connexions, exports, opérations en masse, droits, config).
- [x] **UI dans Admin › Utilisateurs** : (1) journal global filtrable (utilisateur/type/période) sur le sous-ensemble A→E ; (2) par utilisateur sur sa fiche : dernière connexion + résumé actions sensibles. Libellé explicite « traçabilité sécurité/RGPD, pas un suivi d'activité ».
- Priorité conseillée : **login (ok/ko) + export** d'abord, puis le reste + l'UI.

## A faire - Améliorations
- [ ] **Bounces — lire les retours dans la boîte d'ENVOI** *(décidé le 26/09/2026, après le
      festival ; prochaine étape fonctionnelle majeure)*. Aujourd'hui **rien d'opérationnel** : la
      boîte bounce dédiée reste vide, parce que la gestion du bounce est désactivée (rejet 553 de
      LWS sur le Return-Path forcé) — donc l'enveloppe vaut l'adresse d'envoi et **les retours
      s'accumulent dans la boîte d'envoi**. Ce n'est pas un pis-aller : c'est le mécanisme normal,
      à la bonne boîte. Les NDR sont normalisés (RFC 3464, partie `message/delivery-status`), et
      `bounce_scanner._parse_delivery_status()` sait déjà les lire — il n'a jamais eu de boîte
      alimentée.
      **À construire** : un réglage à trois positions (boîte dédiée / boîte d'envoi / désactivé),
      un scan périodique porté par le fil interne (comme `field_refresh`), et la même distinction
      que pour l'envoi — `5.x.x` = définitif, on brûle l'adresse ; `4.x.x` = temporaire, on ne
      touche à rien.
      **Pièges** : on lit une boîte qui sert à autre chose — ne traiter que ce qui a la FORME d'un
      retour (expéditeur `MAILER-DAEMON`, ou partie `delivery-status`), ne toucher ni aux réponses
      de vraies personnes (le Reply-To y ramène du monde) ni aux copies récapitulatives ; déplacer
      les retours traités dans un dossier pour l'idempotence.
      **Cas restant à DISCUTER avec Nicolas** : (a) utiliser une boîte d'envoi spécifique avec le
      Reply-To pointant sur la boîte principale — les retours arriveraient alors seuls dans une
      boîte propre, sans mélange ; (b) **nettoyage automatique des messages de retour** (demandé
      par l'utilisateur) : les supprimer après traitement, ou les archiver, et avec quelle
      rétention. Compter ~1 journée une fois ces deux points tranchés.
- [ ] **gunicorn — sûreté au dédoublement et worker dédié à l'envoi** *(constaté le 26/09/2026)*.
      `--preload` charge l'application dans le processus maître AVANT le fork : `init_db()` étant
      appelé au niveau du module, une connexion SQLite est ouverte dans le maître puis **héritée
      par les deux workers**, qui croient chacun en être seuls propriétaires (« database is
      locked », transactions mêlées — sporadique et difficile à relier à sa cause). Remède : un
      `gunicorn.conf.py` avec un hook `post_fork` appelant `db.engine.dispose()`, pour que chaque
      worker ouvre ses propres connexions.
      **Corollaire vu au passage** : `sending.start_autosend(app)` est lui aussi appelé au niveau
      du module — le fil d'envoi tourne donc **dans le maître**, pas dans les workers (un fil ne
      survit pas au fork). Ça fonctionne, et ça garantit un seul fil, mais le maître n'a pas à
      faire de travail applicatif.
      **Piste retenue avec Nicolas (26/09)** : un **service Docker dédié** à l'envoi, dans le même
      `docker-compose.yml`, lançant `tools/process_queue.py` en boucle. Rien à installer sur les
      hôtes (c'est ce qui avait fait écarter le timer systemd), isolation réelle, logs et
      redémarrage séparés, et le verrou inter-processus garantit déjà qu'un seul envoi tourne.
      Contrepartie : un conteneur de plus par instance, à déployer par claude-serveur.
- [ ] **Lenteur de l'interface — MESURÉE le 26/09/2026, ce n'est ni la base ni gunicorn**. Sur la
      base de dev (1511 contacts, 21 listes) : `/contacts` = 85 ms dont **2,2 ms de SQL**,
      `/listes` = 86 ms dont **2,5 ms de SQL**. Autrement dit **97 % du temps serveur est du rendu
      Python/Jinja**, et la base ne coûte rien.
      Le vrai facteur est le **poids de la page** : `/contacts` envoie **519 Ko pour 100 lignes**,
      soit ~5,3 Ko par contact — le tableau produit **deux lignes par contact** (~2,5 Ko chacune),
      vraisemblablement la vue tableau ET la vue carte du responsive, toutes deux rendues côté
      serveur. Les 5-6 s ressenties viennent donc du navigateur (analyse + rendu) et du réseau,
      pas du serveur.
      **À faire pour trancher en prod** : ajouter `%(D)s` au format des logs d'accès gunicorn pour
      connaître la durée réelle côté serveur, et comparer avec l'onglet Réseau du navigateur. Si
      le serveur répond en 100 ms, le chantier est le poids du HTML (ne pas rendre deux fois
      chaque contact, pagination plus courte, colonnes à la demande).
      **Postgres n'y changerait RIEN** : l'indexation JSON accélère le FILTRAGE sur des champs
      JSON à grande échelle, or ici le SQL représente 2 ms. Cf. la note de décision Postgres.
- [x] **NOÉ — reprise automatique des réponses** *(24/09/2026)*. Les compétences ne descendaient
      que sur un geste humain : « NOÉ fait foi » ne valait que si quelqu'un pensait à cliquer.
      Deux déclencheurs ajoutés (`field_refresh.py`) — **à l'ouverture d'une session**, en tâche
      de fond (connexion mesurée à 0,1 s même avec un service lent), et **à chaque synchronisation**
      des listes. Intervalle minimum **2 h**, horodaté dans un réglage (donc partagé par les deux
      workers et conservé au redémarrage) ; un seul rafraîchissement à la fois ; **aucune création
      de contact** — seuls les bénévoles déjà appariés sont mis à jour. Une seule lecture du projet
      par passe (« Tous les inscrits »), les réponses appartenant à la personne et non au groupe.
      Vérifié contre le vrai NOÉ : 65 bénévoles lus, 8 compétences et 63 formations remontées,
      le filtre « contient AFPS » renvoie les 6 attendus.
- [x] **NOÉ — vocabulaire et questions écartées** *(23/09/2026, retour de Nicolas)*. Deux
      reproches fondés. (1) L'interface disait encore **pôle** et **mission**, mots qui
      n'existent pas dans NOÉ — demande répétée depuis le 15/09, et la doc écrite le même
      jour les reprenait encore. Renommés partout en **Catégories** et **Activités** (UI,
      commentaires, guide) ; les clés internes `category:`/`activity:` portaient déjà les
      bons mots, donc aucune migration. (2) Les deux cases à cocher OBLIGATOIRES (charte,
      consentement) restaient proposées à la correspondance alors qu'on avait convenu de les
      sauter : elles sont désormais écartées comme le téléphone, avec leur raison affichée —
      ce sont des **conditions d'inscription**, acceptées par tout le monde, pas des
      informations sur la personne. Règle : `NoeConnector.skip_reason()` (identité, ou case
      à cocher obligatoire). L'écran ne propose plus que les 3 vraies questions.
- [x] **« Répondre à » absent de l'envoi de test** *(23/09/2026, remonté d'adreic34)*. La
      structure du message était bonne et l'envoi RÉEL portait bien `Reply-To` (vérifié en
      inspectant le message transmis) : c'est `mailing.send_test` qui n'a jamais passé
      `reply_to` à la construction — donc le test, seul moyen de vérifier le réglage, ne
      ressemblait pas au mail envoyé. Corrigé, ainsi que la copie récapitulative de fin de
      campagne qui l'oubliait aussi. Rappel d'usage : `From` reste la boîte d'envoi (SPF/DKIM),
      et un `Reply-To` égal à l'expéditeur ne produit aucun effet visible.
- [x] **Demandes de diffusion : images du corps sorties du HTML** *(23/09/2026, bug adreic34)*.
      Symptômes : aperçu refusé par nginx (`413 Request Entity Too Large`, d'où le passage de
      `client_max_body_size` à 40 Mo), puis retour en arrière réaffichant le mailing SANS les
      images, irrécupérables. **Cause unique** : `imap_submissions` convertissait les images
      inline (`cid:`) en **data URI**, soit +33 % du poids des images DANS le corps — 4,2 Mo de
      photos Gmail = 5,6 Mo de texte traversant la page, l'éditeur, le brouillon `localStorage`
      (quota ~5 Mo) et la requête d'aperçu. Le brouillon ne pouvait plus s'écrire et une version
      PÉRIMÉE, sans images, reprenait la main au retour.
      **Correction** : les `cid:` restent tels quels à la lecture ; « Utiliser » écrit les images
      dans `data/attachments/submission_<uid>/inline/` et les remplace par un lien servi par
      `mailing.submission_inline` (types image seulement, `nosniff`, traversée de chemin
      refusée). Mesuré : corps de **5600 Ko → 214 octets**, page de l'éditeur à 34 Ko.
      À l'ENVOI, `mailer._extract_inline_images` reconnaît ces liens et **réincorpore** les
      images en `cid:` — sinon le destinataire, qui n'a pas de session, verrait des images
      cassées. Les data URI restent gérées (images collées dans l'éditeur). L'aperçu d'une
      demande, lui, incorpore à la volée : rien ne repart en requête derrière.
      Garde-fou : si le brouillon local dépasse le quota, l'ancien est **effacé** au lieu d'être
      laissé en embuscade.
- [ ] **Filtres avancés : plages alphabétiques** *(analysé le 20/09/2026, à coder — ~1/2 journée)*.
      Trois opérateurs sur les champs texte : « commence avant » (`< 'b'`), « commence après »
      (`> 'azz'`), « de … à … » (`>= 'g'` et `< 'q'`). Le moteur est prêt : `OPERATORS_BY_TYPE`
      et `OP_LABELS` alimentent l'UI toute seule (`ADV_META`, contacts.html).
      **Le coût n'est pas le SQL, c'est l'ordre alphabétique** : SQLite compare en binaire,
      donc `'a' > 'Z'` et `'Étienne' > 'Zola'` ; `lower()` n'y change rien (ASCII seul).
      → `alpha_sort_sql(col)` dans `helpers.py` sur le modèle de `phone_digits_sql` (cascade de
      `replace()` + minuscules), marquée `# [PG-PORT]` (Postgres : `unaccent(lower(col))`), et
      **la même normalisation appliquée à la valeur saisie côté Python**.
      **Décision prise** : bornes traitées comme des PRÉFIXES inclusifs — « de G à P » prend
      tout le P (borne haute au caractère suivant, exclusive). Pris au pied de la lettre,
      `<= 'p'` exclurait « Pierre », ce que personne n'attend. Libellés dans ce sens
      (« commence avant », « de … à … »), pas « entre ».
      Détail : ~10 lignes dans `build_predicate`, ~8 dans `custom_field_predicate` (champs
      perso JSON), ~4 lignes de JS (la saisie à deux champs est réservée aux types date/nombre,
      la déclencher sur l'OPÉRATEUR), plus les tests (accents, casse, borne haute, champ vide).
      Réserves : comparaison sur expression → **aucun index utilisable**, balayage de table —
      imperceptible à 3 500 contacts, à revoir au-delà de quelques dizaines de milliers (colonne
      `nom_norm` persistée + index = migration). Le tri des contacts (`order_by(Contact.nom)`)
      souffre du même défaut d'accents : même remède possible, mais **autre chantier**.
- [x] **Envoi asynchrone** *(17-20/09/2026)*. Livraison 1 (v2.4.5) : plafonds aux limites LWS
      (240/h, 2500/j), journal `contact_send` écrit au fil des envois, tranche bornée.
      Livraison 2 (v2.5.0) : confirmer ne fait que mettre en file ; `sending.py` porte la
      boucle, partagée par l'interface, le fil interne et `tools/process_queue.py` ;
      verrou inter-processus ; pause/reprise par campagne ; écran de file avec la marge
      restante. Envoi automatique par **fil interne** (`MAIL_AUTOSEND_INTERVAL`, défaut
      300 s) plutôt qu'un timer sur l'hôte : le verrou règle le problème des 2 workers
      gunicorn qui motivait le timer, et rien n'est à poser sur les serveurs.
      _Mettre `MAIL_AUTOSEND_INTERVAL=0` sur un poste de dev branché sur une messagerie réelle._
- [x] **Reprise automatique et plafond de volume** *(20/09/2026, v2.5.0)*. Un refus TEMPORAIRE
      du serveur (4xx) laisse l'email en file avec une date de reprise (`deferred_until`) au lieu
      de le figer en erreur ; seuls les 5xx restent des échecs. Compteur de VOLUME glissant
      (`MAIL_MAX_MB_PER_HOUR`, défaut 300) sur la taille réelle du message transmis, pièces
      jointes encodées comprises : la tranche s'arrête AVANT le refus de l'hébergeur, au lieu de
      le découvrir en pleine campagne (incident du 18/09, 74 refus `LPR-SIZE01`). Tous les états
      disent quand ça repart (« dans 47 minutes »), et une alerte email part si une campagne se
      termine avec des erreurs définitives (réglage Paramètres, actif par défaut).
- [~] **Quotas mutualisés entre instances** *(20/09/2026 — mesure d'attente prise)*. adreic34, lfll
      et gall envoient depuis le même domaine `asso34.fr` chez LWS, mais chacune compte ses envois
      dans SA base : trois fois le plafond possible. LWS documente DEUX limites indépendantes, par
      boîte ET par domaine (buffer #41) ; **question à poser à LWS** : les 240/h et 2500/j obtenus
      le 15/08 valaient-ils pour la boîte adreic34 ou pour le domaine entier ?
      **En attendant, on applique le plus restrictif** : défauts ramenés à 110/h, 800/j et
      300 Mo/h par instance, soit un tiers des limites connues — les trois instances cumulées
      restent sous les plafonds de domaine génériques (480/h). À remonter dès que LWS répond.
      Reste à faire si le plafond domaine est confirmé serré : un comptage COMMUN aux instances
      (Nicolas écarte un simple fichier dans le dossier docker ; pistes : emplacement système
      dédié, ou petit service partagé sur un réseau interne).
- [x] **Modèles de mailing** *(17/09/2026, branche `feature/modeles-mailing`)*. Table
      `mail_template`, distincte des campagnes : « Enregistrer comme modèle » sur l'aperçu,
      « Partir d'un modèle » dans la rédaction, page Mailing → Modèles (utiliser, renommer,
      supprimer). Partagés entre utilisateurs ; renommer/supprimer : auteur et admins.
      Contenu, pied de mail et pièces jointes (copiées dans `data/attachments/modeles/<id>/`),
      jamais les listes. _Suite possible : « Enregistrer comme modèle » depuis l'historique._
- [x] **Pied de mail — coordonnées de l'association** *(17/09/2026)*. Réglage dans Paramètres,
      option « Coordonnées asso » dans la rédaction (cochée par défaut si renseigné). Les
      options factices de la maquette sont retirées ; « Voir dans le navigateur » abandonnée.
- [ ] **Brouillon et modèle sans liste cochée** *(17/09/2026)*. « Enregistrer le brouillon »
      réutilise la validation de l'envoi (`_persist_campaign_from_form`) : il exige une liste,
      des contacts joignables et SMTP configuré, sans nécessité technique. Proposé : brouillon
      = objet ou corps non vide seulement, identifiant de repli `Brouillon_<date>` ; bouton
      « Enregistrer comme modèle » aussi dans la rédaction, sans condition de liste. L'aperçu
      et l'envoi gardent l'exigence de destinataires.
- [ ] **Pied de mail — nom de la liste et nombre d'inscrits** *(17/09/2026)*. « Vous recevez ce
      mail en tant que membre de la liste X ». À retrouver par destinataire : les listes par
      lesquelles il est visé (un envoi multi-listes en a plusieurs).
- [x] **NOÉ — voir et importer les nouveaux venus** *(23/09/2026)*. Une fois la liste
      rattachée, un bénévole inscrit dans NOÉ après le premier import n'existait nulle part
      pour l'utilisateur : la synchronisation le comptait (`pending`) et le compte finissait
      dans la sortie du timer, que personne ne lit. Le compte est désormais conservé
      (`list_source.pending_count`, migration `migrate_add_source_pending`), affiché en
      pastille « ⚠ N à examiner » sur la liste et sur la page NOÉ, et un écran dédié
      (`/integrations/noe/nouveaux/<source>`) les montre nommément avant de les créer.
      Import en mode « compléter les vides » : une fiche connue est complétée, jamais
      écrasée ni dupliquée — vérifié par test. Avertissements repris de l'écran
      d'alimentation (adresse déjà connue, corbeille, sans email), parce que
      l'appariement se lit sur l'identité externe : quelqu'un présent chez nous sans avoir
      jamais été apparié apparaît comme nouveau. Synchro rejouée dans la foulée pour que
      la liste et le compteur soient justes tout de suite.
- [x] **NOÉ — remonter les réponses du formulaire en champs perso** *(23/09/2026, en attente
      de l'équipe)*. Demande des Fourmilières : segmenter sur les compétences (« As-tu des
      compétences en soin ? », liste à choix MULTIPLES à options fermées), la formation
      Service d'Ordre (Oui/Non), le régime alimentaire (texte libre), et l'opt-in email
      **ajouté au formulaire NOÉ à NOTRE demande pour le RGPD** — il doit donc remonter et
      rester attaché à la fiche. Décisions prises : 1 base = 1 événement NOÉ (pas de
      multi-projet), écriture **à l'import** (la synchro reste inoffensive), mécanisme
      « proposer/valider » écarté (la source est pilotée par l'utilisateur, CM est
      l'esclave), qualité des données à standardiser dans NOÉ par l'équipe.
      **RÉPONDU le 23/09 — méthode 1 : NOÉ FAIT FOI** (les données de CM sont remplacées
      à chaque remontée, les corrections se font dans NOÉ) → mode `overwrite` de l'import.
      **Piège** : `_write_fields` ignore les valeurs vides, donc une compétence RETIRÉE dans
      NOÉ ne serait pas effacée dans CM. Prévoir un `blank_wins` réservé à ce chemin — sans
      toucher à l'import de fichiers, où ignorer le vide reste le bon défaut.
      **Encore en attente** : remontée de l'opt-in, et maintien d'une liste de choix fermée.
      **LOT 1 FAIT (23/09)** : deux régimes selon la DESTINATION, pas la provenance (le
      téléphone vient de `formAnswers` et reste pourtant de l'identité). Identité = le vide
      n'efface jamais, modifiable ici ; champ PILOTÉ (`custom_field_definition.synced_from`,
      migration `migrate_add_field_synced_from`) = reflet du service, le vide efface, non
      modifiable dans la fiche (badge ⟳, garde-fou serveur dans `_apply_form`). Un import de
      FICHIER ne touche pas un champ piloté : il n'est pas la source. `_apply_mapping`
      conserve désormais les clés vides — sans quoi un effacement ne parvenait jamais à
      l'écriture ; sans effet sur l'import de fichiers, vérifié par test.
      **LOT 2 FAIT (23/09)** : page « Réponses du formulaire » (`/integrations/noe/champs`,
      admin) — chaque question du formulaire NOÉ se dirige vers un champ perso, existant ou
      créé à la volée, et le champ choisi devient piloté (`synced_from='noe'`) ; retiré de la
      correspondance, il redevient libre. La correspondance vit dans le réglage
      `noe.field_map` (JSON), une seule par instance — 1 base = 1 événement. `noe.py`
      transporte les réponses brutes, le connecteur les traduit (`format_answer` : choix
      multiples joints par « ; », booléens en Oui/Non, absence = vide qui EFFACE).
      **Ajouté en cours de route** : bouton « ⟳ Actualiser les réponses depuis NOÉ » sur
      l'écran des nouveaux venus — sans lui, rien ne mettait à jour les bénévoles DÉJÀ
      connus, et « NOÉ fait foi » restait lettre morte. Actualisation en mode « compléter
      les vides » : l'identité corrigée chez nous survit, les champs pilotés sont remplacés
      de toute façon (le régime du champ prime sur le mode d'import).
      **Questions réelles du projet lfll** (lues le 23/09) : `astuDesCompetencesEnSoin_3z2`
      est bien un **multiSelect** — la liste fermée est confirmée, le lot 3 a donc du sens ;
      `jaccepteDeRecevoirParEmailLesI_b4z` (opt-in) et `jaiLuLaCharteEtJeMengageALaRes_lni`
      sont des cases à cocher ; régime alimentaire en texte libre.
      **LOT 3 FAIT (23/09)** : type de champ **« choix multiples »** — valeurs stockées en
      LISTE JSON, opérateurs `has_any` / `has_all` / `has_none` évalués sur les ÉLÉMENTS
      (`json_each`, balisé `[PG-PORT]`) et non sur le texte du JSON : « Médecin » n'attrape
      pas « Médecin du travail », et l'échappement des accents (`\u00e9`) rend de toute
      façon un LIKE faux. Saisie par cases à cocher, rendu « AFPS, medecin » en variable de
      mailing, options proposées dans le constructeur de filtres.
      **Découverte du 23/09** : les réponses NOÉ stockent la VALEUR TECHNIQUE (`afps_osy`),
      pas le libellé — sans traduction la fiche affichait du charabia. `form_fields()`
      remonte désormais la table valeur→libellé, et un champ créé depuis une question naît
      avec son type (multiSelect → choix multiples, radioGroup → liste) et ses options.
      Deux bugs trouvés en test et corrigés : paramètres SQL homonymes (deux conditions sur
      le même champ, la seconde écrasait la première — `has_all` répondait juste par
      accident) et négation impossible sur un fragment SQL brut (`NOT EXISTS` écrit à la main).
- [x] **NOÉ — sort de l'opt-in email** *(23/09/2026, tranché)*. L'équipe considère que
      **l'acceptation de la charte vaut acceptation d'être contacté** pour la fonction de
      bénévole : les deux cases font doublon, et l'opt-out reste le lien de désabonnement de
      nos mailings. Donc **pas de destination « Consentement »** — les cases restent des
      champs informatifs si on veut en garder la trace.
      **Mesure faite avant de décider** (64 inscriptions) : opt-in coché par 41 (64 %),
      **absent chez 23 (35 %)** — inscrits avant l'ajout de la case — et **0 décoché**, la
      case étant obligatoire (elle prouve un consentement, elle ne permet pas de le
      refuser). Traiter « absent » comme un refus aurait désabonné un tiers des bénévoles.
      Si le sujet revient : **trois états**, absent = question non posée = on ne touche à rien.
- [x] **NOÉ — questions d'identité non mappables** *(23/09/2026)*. « Numero de tel » est déjà
      repris par le connecteur via son TYPE (`phoneNumber`), en régime identité. La proposer
      à la correspondance créerait un doublon, et mappée vers un champ piloté elle passerait
      en régime reflet — un bénévole vidant sa réponse effacerait le numéro saisi chez nous.
      Elle s'affiche donc sans être proposée (« déjà repris dans Téléphone »), avec un
      garde-fou côté serveur. Règle générale : `IDENTITY_TYPES` du connecteur. **À trancher ensuite** : type multi-valeurs
      propre (stockage liste JSON + opérateurs « contient l'un de ») vs texte à séparateurs
      — les options venant d'une liste fermée, le type propre vaut le coup pour que les
      segments soient exacts. Mapping mémorisé (les clés NOÉ sont suffixées : `soin_3kd`) ;
      `ImportMapping` répond déjà à ce besoin. Précédent réutilisable : `../noe-outils/`
      module `catering` lit déjà une réponse de formulaire (régime alimentaire), avec tests.
- [ ] **NOÉ — avertir du risque de doublon pôle / mission** *(10/09/2026)*. Depuis que les
      deux niveaux sont alimentables, une même personne peut se retrouver dans une liste
      « pôle » ET dans une liste « mission » qui en dépend — chez lfll, « Accueil » (11) et
      « Accueil Public - Entrée » (10) se recouvrent presque entièrement. Un envoi visant
      les deux listes à la fois dédoublonne par email (personne ne reçoit deux fois le même
      message), mais **deux envois séparés arrivent bien deux fois**. À afficher là où le
      choix se fait : sur l'écran d'alimentation (« ce groupe recoupe une liste déjà
      alimentée : N personnes en commun ») et/ou sur le composeur quand deux listes
      sélectionnées se recouvrent fortement. Décision utilisateurs : on laisse les deux
      niveaux ouverts, on documente le risque.
- [x] **NOÉ — reprendre exactement les intitulés de NOÉ dans l'interface** *(demandé le 15/09, FAIT le 23/09)*.
      L'intégration dit « pôle » et « mission », mots qui n'existent pas dans NOÉ : les
      utilisateurs ne retrouvent pas ce qu'ils voient dans NOÉ. Intitulés vérifiés dans le
      code source de NOÉ (via noe-outils) : **Catégorie** (`categories`), **Activité**
      (`activities`), **Session** (`sessions`), **Espace** (`places`), **Encadrant·e**
      (`stewards`). Les références internes `category:` / `activity:` sont déjà les bons
      mots, seuls les libellés affichés changent (pages `/integrations/noe`, choix du
      niveau, messages, point « doublon pôle / mission » ci-dessus). Attention à la nuance
      NOÉ : sur une activité, « Encadrant⋅es **éligibles** » et « Espaces **éligibles** »
      sont des viviers ; l'affectation réelle est sur la session.
- [ ] **Tags transverses (n↔m) sur les objets** — *idée à réfléchir, 10/09/2026.* Une table
      d'étiquettes partagée entre plusieurs types d'objets (listes, contacts, et pourquoi pas
      campagnes ou formulaires) plutôt qu'un champ par entité. Saisie des tags sur la fiche
      d'une liste et sur celle d'un contact, puis **sélection par tag** : « toutes les listes
      du festival », « les contacts marqués bénévole ». À creuser avant de coder :
      articulation avec l'existant — les Listes sont déjà un regroupement de contacts, et
      `ContactSegment` (filtres nommés) couvre une partie du besoin côté contacts ; risque
      de trois mécanismes voisins. Voir aussi si les tags doivent être libres ou choisis
      dans un référentiel, et ce qu'ils deviennent sur une liste alimentée par une source
      externe (donnée locale, non écrasée par la synchro — cf. `list_source`).
- [x] Export vCard (réutiliser vcard_converter.py en sens inverse)
- [~] Historique des campagnes envoyées (historique messages, envois // reste à faire : historique par contact)
- [x] Spinner overlay "Envoi en cours" sur le bouton de lancement de campagne
- [x] Pièces jointes dans les mailings (upload, stockage, envoi MIMEBase)
- [x] Affichage du message dans la file d'attente : toggle afficher/masquer, rendu HTML via iframe
- [~] Historique mailing : affichage du détail d'une campagne (corps du mail, liste, pièces jointes) — clic sur ligne ou bouton dédié
- [x] Envoi asynchrone (ne pas bloquer l'interface pendant l'envoi)
- [x] Pagination de la liste des contacts (Lot A refonte : pagination client 25/page, sélection conservée entre pages)
- [x] Cache-busting des assets statiques (fait : ?v=mtime via global Jinja asset_version) (`?v={{ config.APP_VERSION }}` sur style.css / JS) — évite que le navigateur serve un ancien CSS après déploiement (piège rencontré en test refonte : Ctrl+Shift+R nécessaire)
- [x] **Segments dynamiques accessibles à l'utilisateur** (décision 22/07 ; **PARTIEL** : filtre Statut Abonnés/Désabonnés/Bounces ajouté en Lot A — reste « jamais mailés » + corbeille comme vues) : donner accès depuis la page Contacts
  aux sélections calculées — **désabonnés**, **bounces** (`has_bounced`), **jamais mailés**, corbeille — sous forme de
  filtres/vues. Aujourd'hui la page Contacts ne filtre que par liste / source / recherche → impossible de voir les
  désabonnés. Les listes restent l'outil end-user "curé" ; les segments sont l'outil dynamique, mais ils doivent être
  **manipulables par l'utilisateur**, pas seulement internes. (Version ultérieure, validé.)
- [x] Recherche avancée (filtres multiples)
- [ ] Fusionner deux listes
- [x] **Stats de formulaires (ouverts / répondus)** — la seule métrique « ouverture/clic » qui a du sens en non-marchand, et quasi gratuite : le clic atterrit chez nous. GET page publique = **ouvert**, POST = **répondu**. Compter/afficher par formulaire (taux de réponse). Pas de tracker externe, pas de pixel — respectueux.
- [x] **Garde-fou volume d'envoi** — le vrai plafond = quota du serveur mail (`mail.aubaygues.fr`), pas la réputation (base 100 % opt-in). Ajouter : **cap quotidien configurable** + **avertissement au-delà d'un seuil** (ex. > 500 en un envoi) + conseil de **montée en charge progressive** (warm-up). Le pacing existe déjà (`MAIL_RATE_PER_MINUTE=20` → 3 s/email) + file d'attente. Pré-requis délivrabilité à vérifier : **SPF/DKIM/DMARC** sur aubaygues.fr. **📄 Mémo complet : `doc-travail/delivrabilite-envoi.md`.**
- [ ] **⚙️ ACTION — demander à l'admin de `mail.aubaygues.fr` ses quotas d'envoi** (par heure / par jour) → c'est le plafond dur qui conditionne la taille des envois. **+ vérifier SPF/DKIM/DMARC** sur `aubaygues.fr` avant tout envoi élargi. Cf. `doc-travail/delivrabilite-envoi.md`.
- [~] Export vCard : route disponible (3.0/4.0), compatibilité Thunderbird à investiguer

## RGPD / données personnelles (à traiter avec soin)
- [ ] **Suppression d'un utilisateur — stratégie RGPD** (actuellement `users.delete` = hard delete sec). Constat : `MailCampaign.sent_by` est un snapshot texte (historique campagnes SAIN, non impacté) ; mais `Contact.created_by_id/updated_by_id/deleted_by_id` + `PreferenceForm.created_by_id` sont des FK vers user → sur SQLite (FK non appliquées) le delete laisse des refs orphelines (lectures gardées → « — », pas de crash) ; **planterait** si FK activées / Postgres (pas de try/except). 
  - **Préférence retenue (à discuter au moment du traitement)** : plutôt **nullation** des refs OU **obfuscation destructive** des données signifiantes de l'utilisateur, en **laissant les historiques consultables** (plus simple à gérer que tout supprimer). Privilégier la **désactivation** (déjà là) comme geste normal ; la suppression = purge exceptionnelle (droit à l'effacement).
  - Fix technique associé : nuller les refs + try/except à la suppression ; à terme `PRAGMA foreign_keys=ON` + `ondelete='SET NULL'`. Doit être **carré** côté conformité.
- [ ] Vérifier plus largement les autres surfaces RGPD (export/effacement des données d'un contact, consentement formulaires, rétention).

## Robustesse du service (analyse 2026-07-18)
- [x] File d'envoi migrée du fichier JSON vers la DB (tables mail_campaign / mail_queue_item, colonnes JSON pour snapshot contact + PJ). Écritures transactionnelles, ids auto-incrémentés (fin des collisions), sauvegardé avec la DB. Interface MailQueue inchangée. Migration : tools/migrate_queue_to_db.py. (tools/fix_queue_ids.py devient obsolète.)
- [x] Timeout IMAP dans le chemin des requêtes (`IMAP4_SSL(..., timeout=10)`) — évite le gel d'un worker si le serveur mail ne répond pas
- [x] Ajouter la protection CSRF (Flask-WTF) sur les formulaires POST — *25/09/2026* : `CSRFProtect`, jeton dans les 80 formulaires, en-tête `X-CSRFToken` ajouté automatiquement aux appels `fetch`, et message compréhensible quand la page a expiré (différent selon qu'on est connecté ou visiteur d'un formulaire public).
- [ ] Fork-safety : `init_db()`/`db.engine.dispose()` en post_fork (gunicorn --preload) ; assert SECRET_KEY ≠ défaut en prod
- [x] **Point d'entrée unique des migrations `tools/migrate.py`** (runner ledger `schema_migrations`, registre ordonné des 21 scripts, `--dry-run`/`--stamp`/`--safe-only`) — **Fait (05/08, dans l'image v2.0.0)**. À chaque changement de schéma : ajouter une ligne dans `MIGRATIONS`. Après déploiement : `docker compose run --rm --no-deps app python tools/migrate.py` (`run` et non `exec` : si le nouveau code attend une colonne pas encore créée, l'app boucle au démarrage et `exec` n'a aucun conteneur où s'accrocher — cf. en-tête de `tools/migrate.py`). *(Alembic reporté au jour Postgres.)*
- [ ] **🧹 Assainir `update.sh` (dépôt `contact-mailer-deploy`), à froid** : la version qui tourne sur lfll/adreic34 est **hors git** (modifiée à la main depuis ~17/07), **prune inconditionnel** (tue le rollback), **backup `data/` seulement**, **n'appelle pas `migrate.py`**. → committer la vraie version, retirer/optionnaliser le prune, backup db+.env+compose, **câbler `migrate.py` après le restart**. En attendant = **déploiement MANUEL**. Cf. [[deploy-and-migrations-cleanup]].
- [ ] (Confort) WAL SQLite, pages d'erreur 404/500 personnalisées, envoi asynchrone si les listes grossissent
- [ ] **Portabilité moteur DB — SQLite → Postgres (audit 2026-07-27)** : couche d'accès **saine** (100 % ORM, aucun SQL brut, URI **env-driven** `SQLALCHEMY_DATABASE_URI`, `.ilike`/`db.JSON` portables ; un Postgres **neuf** marche via `db.create_all()`). **Bascule = coût faible et borné, pas de réécriture.** 2 chantiers à traiter le jour où on bascule :
  - [ ] **Migrations → Alembic / Flask-Migrate** : les ~10 `tools/migrate_*.py` sont en **`sqlite3` brut + PRAGMA** → non portables. Converger vers Alembic (engine-agnostic) ; ne concerne que l'évolution in-place (pas un déploiement neuf). Cf. [[deploy-and-migrations-cleanup]].
  - [ ] **Fiabiliser les hard-deletes (contraintes FK)** : SQLite n'applique pas les FK, **Postgres oui** → `users.delete` (+ `FieldProposal`, refs `*_by_id` de Contact/PreferenceForm) lèverait une **violation FK**. Nuller les refs / `ondelete='SET NULL'` + activer `PRAGMA foreign_keys=ON` en dev pour dé-risquer tôt. **Recoupe l'item RGPD** (suppression utilisateur). Les relations en `cascade='all, delete-orphan'` sont déjà propres.
  - [ ] Ops bascule : ajouter `psycopg2`, service Postgres, ETL one-shot des données (ex. `pgloader`).
  - **Note de décision (21/09/2026)** — Nicolas : « il est temps de passer à un vrai SGBDR ».
    Réponse : **oui pour Postgres le jour où on le fera, non maintenant.** Ce n'est pas une
    question de code — la couche d'accès reste saine, le seul SQL spécifique est
    `json_extract` des champs perso, isolé et balisé `# [PG-PORT]` dans `contact_filters.py`.
    **Chiffre actualisé : 34 scripts `tools/migrate_*.py` en `sqlite3` brut, dont 24 avec
    `PRAGMA table_info`** (l'audit de juillet en comptait ~10). C'est l'outillage entier qu'il
    faut reprendre, plus la sauvegarde : aujourd'hui un `cp` de fichier, demain des dumps, un
    service de plus par hôte, un compte par instance — et c'est claude-serveur qui opère.
    **Ce qui ne le justifie pas** : le volume (3 500 contacts) ni la concurrence — SQLite en WAL
    encaisse le fil d'envoi, le web et le scan IMAP à cette échelle.
    **Ce qui pourrait le justifier** : (a) la comparaison de texte avec accents — `unaccent` et
    les collations ICU régleraient d'un coup les plages alphabétiques ET le tri ; mais ça se
    résout sans changer de moteur ; (b) le compteur de quota commun aux trois instances — qui
    appelle un **service partagé**, pas une base commune : les instances hébergent des
    associations différentes et le cloisonnement des données est un choix à ne pas défaire.
    **MariaDB écarté** : ni `jsonb` indexable ni `unaccent`, et le code est balisé pour Postgres.
    **Critère pour trancher, à froid** : mesurer avant de décider — « database is locked » dans
    les logs, temps de réponse des listes, taille des bases. Un symptôme chiffré ouvre le
    chantier ; une impression, non.

## Session debug 2026-07 (régressions post-restructuration blueprints)
- [x] Bouton « Envoyer un email de test » : câbler la route POST /mailing/test-smtp (existe déjà) dans la page **Généraux** — *renommage « Paramètres »→« Généraux » **FAIT** 26/07 ; reste à câbler le bouton*
- [x] Régler le bloqueur bounce 553 (MAIL FROM=bounce@ rejeté par le SMTP) — fait 26/07 : fonction bounce **retirée du `.env`** (BOUNCE_RETURN_PATH/IMAP vidés) → enveloppe = compte SMTP authentifié. **À répliquer en prod lfll.** (Le toggle UI « Gestion du Bounce » reste à faire, voir plus bas.)
- [ ] Test exhaustif bouton par bouton : Mailing (M1–M18) puis Formulaires (F1–F11)
- [ ] Mailing/P2 — gestion de l'absence de Civilité : la civilité reste optionnelle (respect / non-binaire), donc `{civilite}` peut être vide → l'assistant variables (P2) doit aider à gérer l'absence proprement (ex. `{civilite:{civilite} :}` conditionnel, ou salutation neutre par défaut) pour éviter les « Bonjour ,  Nom » disgracieux. (L'accord de genre, lui, est réglé : « Inclusif » par défaut, jamais vide.)
- [x] Éditeur mailing : passer l'UI/commandes en français ; ajouter un bouton « insérer une image » (seul Ctrl+V/Ctrl+C fonctionne)
  - EN ATTENTE de la proposition UI de Claude Design avant de trancher l'éditeur. Faits établis (2026-07-18) : version actuelle **TinyMCE 6.8.5**, dernière **8.8.0**. Depuis la v7, auto-hébergement en GPLv2+ exige `license_key: 'gpl'` (gratuit) ; en **v8, sans clé l'éditeur passe en lecture seule**. Options : garder 6.8.5 (OK, aucune clé) / upgrade 8.8.0 + `license_key:'gpl'` / remplacer par TipTap ou Unlayer (builder email, merge-tags cliquables). Ne pas migrer avant de savoir si on garde TinyMCE.
- [ ] Bouton « Envoyer X emails maintenant » : feedback visuel selon le résultat — échec → rouge + texte « Recommencer… » / « Afficher le log de l'envoi » ; succès → vert + texte différent de celui d'avant l'envoi
- [x] File d'envoi — état « terminé » : alerte de succès verte « ✓ Campagne envoyée » (mailing_queue.html)
- [x] File d'envoi — DANGER UX : bouton « Supprimer la campagne » remplacé par « ← Retour aux mailings » (vers mailing.history). Suppression toujours possible depuis l'historique
- [x] BUG : après envoi, item reste « En attente » — cause = ids non uniques (len()+1 recyclé après suppression de campagnes) → mark_sent/mark_error frappent le mauvais item. Corrigé (id=max+1) + outil tools/fix_queue_ids.py pour les fichiers existants
- [x] Demandes de diffusion — liste : pouvoir prévisualiser le CONTENU du mail (corps + PJ) directement depuis la liste, AVANT « Utiliser pour un mailing »
- [ ] Demandes de diffusion — traçabilité expéditeur : conserver l'adresse du demandeur (en pied de mail / métadonnée) pour lui renvoyer un compte-rendu d'exécution du mailing (qui a validé + infos du mailing envoyé)
- [ ] Demandes de diffusion — signature de modération (contexte MILITANT / confidentialité) : afficher par défaut en pied des mailings ISSUS d'une demande (campagne avec submission_id) une ligne « demande de diffusion modérée par : <signature> ». GARDE-FOUS :
  1. Découpler **audit interne** (toujours stocker le vrai `user_id` du modérateur sur la campagne — aujourd'hui `sent_by` en texte, préférer un user_id — visible **admins seulement**) de la **signature externe**.
  2. Nouveau champ `User.moderator_signature` (texte libre, optionnel, **distinct de `display_name`** qui = prénom+nom réel). **JAMAIS** de repli sur nom réel / username.
  3. **Vide = AUCUNE ligne** (défaut sûr) — ou libellé générique type « l'équipe ».
  4. UI **explicite** : le champ est public (« ce nom apparaîtra en bas des diffusions que vous modérez »).
  5. Interrupteur **« signer cette diffusion »** à l'envoi (exposition contextuelle, décoché par défaut si pas de signature).
  Limite à documenter côté UI/doc : un email est transférable/archivable/découvrable → c'est de la **réduction de surface, pas de l'anonymat garanti**.
- [ ] Demandes de diffusion — UX pièces jointes : la PJ d'une demande n'apparaît PAS dans le champ habituel des pièces jointes, mais comme case « Ajouter à l'envoi » décochée dans l'encart bleu (mailing.html:37) → trop facile à manquer, on envoie sans la PJ. À rendre évident (pré-cocher ? remonter dans la zone PJ standard ? avertir si non cochée à l'envoi)
- [ ] Demandes de diffusion — archivées invisibles : le bouton « Archiver » déplace vers le dossier IMAP `Traite`, mais AUCUNE vue in-app ne permet de consulter les demandes archivées (submissions() ne scanne que INBOX). Ajouter un affichage des demandes archivées
- [x] BUG lien formulaire cassé dans l'email (http://p/... NXDOMAIN) : TinyMCE relativisait les URLs same-domain (convert_urls défaut=true). Corrigé dans mailing.html (convert_urls/relative_urls/remove_script_host = false). NB : ne se manifestait que quand domaine du lien == domaine de l'app (cas prod). À redéployer (v1.2.12) pour lfll.
- [x] Formulaire — page de confirmation (« Préférences enregistrées ») : bouton « Revoir mes choix » (relien vers /p/token/uid) + note de réouverture via le lien email
- [ ] Formulaire — sécurité du lien public : token + uid permanents, pas d'expiration par lien → un formulaire sans date de clôture = lien bearer permanent (consultation/modif des abonnements du contact ad vitam). Suggérer/imposer une date de clôture ; envisager expiration/rotation du lien. Cf. [[formulaires-next-subjects]]
- [ ] Formulaires — sémantique d'édition & versionnement (DESIGN, à trancher avec la refonte) :
  aujourd'hui l'édition modifie le formulaire EN PLACE (même id, même token, même lien) → tous les
  visiteurs suivants voient la version modifiée ; `PreferenceResponse` ne stocke aucun snapshot
  (juste contact_id/form_id/date), donc anciennes et nouvelles réponses sont indissociables.
  3 options : (A) édition en place [actuel] ; (B) versionnement = une modif structurelle crée une
  NOUVELLE instance (nouvel id/token/lien), l'ancienne figée ; (C) snapshot JSON dans
  PreferenceResponse (ce qui était proposé/coché) pour rester interprétable après édition.
  → Reco cible petites structures : garder A + le verrou ci-dessous + éventuellement C.
- [x] Formulaires — VERROU structurel (FAIT F2 : UI cases désactivées + bandeau explicatif + enforcement SERVEUR — le jeu de groupes est figé si le formulaire est ouvert, vérifié) tant que le formulaire est ouvert (is_active ET date de
  clôture non dépassée) : interdire l'AJOUT/RETRAIT de listes, n'autoriser que les retouches de
  texte (nom, description, label/help de chaque liste, ordre) + la date de clôture. Pour
  restructurer : clore d'abord le formulaire (déverrouille). Enforcement SERVEUR obligatoire
  (edit() ignore tout changement du jeu de liste_ids si ouvert), + UI : cases de listes
  désactivées avec bandeau explicatif. NB : garde-fou anti-erreur, pas une garantie d'intégrité
  totale (compléter par l'option C si l'auditabilité compte).
- [x] Formulaire (édition/création) : contraint sur une demi-page (form-card max-width 600px) → modificateur .form-card-wide (max-width:none) sur formulaire_edit
- [x] Mineur — page « confirmation de l'envoi » : toggle « tout sélectionner » coché par défaut (mailing_confirm.html)
- [ ] Documentation utilisateur : rédiger une vraie doc par fonction (menus Mailing, Formulaires, Contacts, Listes, Paramètres… chaque bouton/action), destinée aux utilisateurs finaux des petites structures
- [x] Paramètres : ajouter une case à cocher « Gestion du Bounce » (activer/désactiver). Sur les petites structures (cœur de cible de l'app), le suivi des bounces n'est pas indispensable → permettre de le désactiver proprement dans l'UI, au lieu de bidouiller les variables .env (quand OFF : pas d'adresse bounce forcée en enveloppe → règle aussi le rejet SMTP 553)
- [x] Page "Listes" : bouton « Exporter » désormais affiché uniquement si current_user.is_admin (listes.html)


## ═══════════ REFONTE v2 (chantier UI/UX — sessions juillet 2026) ═══════════
# Branche `design/claude-design-v2`. Refonte écran par écran, chaque écran mené à 100 %.

### Fait
- [x] **P0 — Fondation** : design system v2 (tokens indigo/crème), shell **sidebar gauche** (Travail/Configuration + bloc user)
- [x] **P1 — Fiche contact** refondue (page pleine, sections/cartes pilotées par le registre `fields.py`) + backend **champs personnalisés** (`Contact.custom_fields` JSON, `CustomFieldDefinition`, écran admin CRUD) + civilité / accord de genre
- [x] **Contacts (liste)** — conforme CLD 01a/01b : en-tête (Importer/Nouveau + sous-titre), barre d'outils (recherche + filtres Liste/Statut en pills + Corbeille), avatars + nom/email empilés, **statut = point** (vert/rouge/ambre), colonnes triables, **pagination client**, **résumé étendu au clic** (desktop accordéon + carte dépliable mobile), ✎ édition, mailto:/tel: (numéro nettoyé). Bandeau de sélection : Ajouter/Transférer/Retirer d'une liste, **(dés)abonner à statut variable** (tracé), Exporter (par ids), Corbeille. **Sélection persistante entre filtres** + vidée après action + conservée à l'aller-retour ✎
- [x] **Listes** — refonte v2 (tuiles stats, pastilles couleur choisies, actions en icônes, archivage réversible, colonne « dernier usage », modales créer/éditer/supprimer) — validé 100 %
- [x] **Utilisateurs** — refonte v2 (email sous le nom, actions en icônes, création/édition en modale, signature de modération)
- [x] **Mailing** — composer v2 (éditeur **TinyMCE 6 auto-hébergé en français**, boutons Variable/Lien formulaire/Image en **CID** privé), multi-listes + dédoublonnage, **parcours d'envoi 4 étapes** (Composer→Aperçu→Destinataires→Envoi) avec barre d'étapes + modale de confirmation + état de succès
- [x] **Navigation** — sous-nav Mailing réordonnée (Historique · Demandes · File) ; **Paramètres** : sidebar locale retirée → **sous-nav dans la sidebar principale** (Généraux · Champs personnalisés · Corbeilles) ; page **« Paramètres »→« Généraux »** ; nouvelle page **Corbeilles** (extensible) ; section **Intégrations** niveau 1 (Seafile · BookStack)
- [x] **Données (dev)** — nettoyage des faux doublons de test + des `titre="None"`

### À faire — Refonte v2 (backlog accumulé, à traiter plus tard)
**Écrans restants (dans l'ordre) :**
- [x] **C. Fiche contact — sécurité & navigation (retours #24)** — **Fait (08-04)** :
  - [x] (a) **Ouverture en VISION (lecture seule) + bouton « Modifier »** : route `contacts.view(id)` (même template piloté par `fields.py`, flag `readonly`). Liens externes (onglet Réponses formulaire) → vision ; lien « Voir la fiche » dans la liste ; l'accordéon inline reste la vision rapide ; ✎ → édition directe.
  - [x] (b) **Précédent / Suivant** sur la fiche vision : séquence d'IDs (liste filtrée serveur, triée/paginée client) déposée en `sessionStorage` au clic ; voisins cycliques ; masqué si lien direct. *(Réutilisation en édition = possible plus tard, même mécanisme.)*
  - [x] **Export CSV réponses = `@admin_required`** + bouton masqué pour non-admin.
- [x] **E. Mailing — historique + file globale** — **Fait (08-04)**. Polish : actions en icônes + « Supprimer » sécurisé (déjà en place) ; badges unifiés + `<style>` sorti dans `style.css`.
  - [x] **G1 — File d'attente = uniquement le NON-expédié**, groupé par campagne (en attente + erreurs), « Reprendre l'envoi » ; une campagne 100 % envoyée n'y figure plus. Titre « · à envoyer ». *(Corrige le non-sens « campagne envoyée = en attente ».)*
  - [x] **G2 — Historique = revue pour TOUTES les campagnes** : 👁 « Voir les destinataires / détail » toujours affichée + cellule Stats cliquable ; page détail = « Détail des envois » (destinataires + statut) dépliée par défaut, contrôles d'envoi conditionnels au reste à faire.
  - [x] **G3 — Tri client** des colonnes historique (Date/Envoyé par/Stats).
- [ ] **F. Formulaires** — refonte cartes (statut Actif/Expire/Archivé, validité, nb réponses) + net-new (RGPD, apparence, aperçu) — cf. gros sujets Formulaires plus haut
  - [x] **F1** liste en cartes · [x] **F2** édition en sections + verrou structurel + ordre des groupes (droplist + ↑/↓) — commités
  - [ ] **F2 à REPENSER (pause 27/07 — usage/utilisabilité, #21-F2)** :
    - (a) **Verrou trop agressif** : un formulaire ACTIF mais **jamais utilisé (0 réponse)** doit rester **librement modifiable**. Aujourd'hui il faut désactiver → enregistrer → rééditer. → baser le verrou sur « **a des réponses** » (responses > 0) plutôt que sur « actif ».
    - (b) **Bug « None »** dans le champ Explication (info-bulle) quand `help_text` est vide (Jinja rend `None` = « None ») → `{{ (fl.help_text if fl else '') or '' }}`.
    - (c) Repenser plus globalement l'ergonomie de l'édition (retour utilisateur).
  - [ ] **F1 polish (#21)** : nom du formulaire en **bleu cliquable** ; redondance nom-lien vs bouton « Réponses » à trancher.

### ⭐ Formulaires v2 — ARCHITECTURE (décisions actées avec CLD, 2026-07-27)
- **Un formulaire = description + N blocs typés** (assembleur de blocs, pas 2 écrans séparés). Régime de sécurité PAR bloc :
  - **`listes`** (préférences, l'actuel) : cases = Listes, écrit sur `Contact.listes`. Régime **direct** (token+uid+clôture). ✅ existe.
  - **`sondage`** (cas 2, champs HORS base) : réponses en **stockage isolé** (jamais sur la fiche canonique). Régime **direct** — même niveau que les listes (pas de lecture de données existantes, pas d'écrasement). Échappement en sortie obligatoire.
  - **`fiche`** (cas 1, champs de la BASE) : édition de champs canoniques. Régime **validation admin** (propose→valide). 
- **OTP découplé du pré-remplissage** (insight clé) : l'OTP ne sert qu'à sécuriser le **pré-remplissage** (exposition en LECTURE des données existantes).
  - **v1 (reco)** : bloc `fiche` en **write-only** (pas de pré-remplissage) + **validation admin** → zéro exposition lecture, écriture neutralisée, **PAS d'OTP**. Plus simple + plus respectueux de la donnée (aligné militant).
  - **v2 (confort)** : pré-remplissage (le contact voit/corrige ses valeurs) → **OTP à la demande** (code envoyé quand il ouvre la page, **JAMAIS dans le mail du lien**) + session courte + expiry.
- **Liste blanche des champs éditables** = sous-ensemble de `fields.py` `contact_fields()` **hors `RESERVED_KEYS`** (email/uid/listes). Typage/libellés déjà fournis par le registre.
- **Clôture OBLIGATOIRE** dès qu'un bloc `fiche` est exposé (réduit la fenêtre de fuite du lien).
- **Modèle de données** : `FormBlock(form_id, type, ordre, config JSON)` ; étendre `PreferenceResponse` (`data` JSON + `status` pending/applied/rejected + `applied_by`) = file **« modifications proposées »**. Écran admin de modération (même mental model que demandes de diffusion / corbeille).
- **⚠️ Transverse — auth ≠ sanitisation** (dès qu'un contact écrit, cas 1 OU 2) : échappement à TOUS les points de sortie de NOTRE code : `mailer` (HTML), `imports.export_contacts` TSV (**préfixer `= + - @`** anti-formula-injection Excel), `export_vcard`, affichage admin. \+ **rate-limit** sur l'envoi OTP (anti-flood boîte), \+ **CSRF** sur la session OTP.
- **Périmètre v2** : refonte préférences + **ossature de l'assembleur** + blocs faibles (listes ✅, sondage) ; **différer le public cas 1**, ou le livrer en **write-only + validation (sans OTP)**.

### 🗺️ Formulaires v2 — PLAN D'ATTAQUE (handoff CLD `update_formulaires`, écrans 04a→04e2d)
> Le design CLD valide notre archi. F1/F2/F3 déjà livrés sont **pré-assembleur** → partiellement réabsorbés (F1→M7, F2→M3, F3→M2/M5).

**Fondations (données)**
- [x] **M1 — Modèle de données** (migrations `migrate_*`, backup + dry-run) :
  - `FormBlock(id, form_id, type ∈ {listes,sondage,fiche}, ordre, config JSON)` — migrer les `PreferenceFormListe` existants en un bloc `listes`.
  - `SurveyQuestion(id, block_id, ordre, label, type ∈ {oui_non, texte_court, …})` (bloc sondage).
  - bloc `fiche` : config = liste blanche de `field_key` (issus de `fields.py`, hors RESERVED).
  - `PreferenceResponse` étendu : `data` JSON (listes choisies + réponses sondage).
  - `FieldProposal(id, form_id, contact_id, field_key, old_value, new_value, status ∈ {pending,applied,rejected}, otp_verified, proposed_at, reviewed_by, reviewed_at)` = file « À valider ».
  - *(Phase 2)* `FormAccessCode(form_id, contact_uid, code_hash, expires_at, attempts)` (OTP).

**Admin — le formulaire devient UNE page à ONGLETS** (Édition · Lien · Réponses · À valider·N)
- [x] **M2 — Coque onglets** : en-tête (← Formulaires + titre + statut + Aperçu + Archiver) + navigation par onglets (remplace pages détail/édition séparées).
- [x] **M3 — Onglet Édition = éditeur en BLOCS** (M3a ossature+verrou affiné · M3b bloc fiche · M3c bloc sondage) : Réglages généraux (message d'accueil, date de validité + **garde-fou clôture obligatoire si bloc fiche**) ; « Contenu du formulaire » = blocs empilables réordonnables, chacun **badgé** (Accès direct / OTP+validation) avec son éditeur : listes (↑/↓ + droplist — **réutilise F2**) · sondage (questions + type) · fiche (**liste blanche groupée depuis le registre**, email 🔒 verrouillé).
- [x] **M4 — Onglet Lien** : URL + copier + bandeaux (OTP si fiche · lien nominatif) + validité.
- [x] **M5 — Onglet Réponses** : cartes (contact + listes choisies + réponses sondage) + **Exporter CSV** (échappé).
- [x] **M6 — Onglet À valider** : file « modifications proposées » (diff **ancien→nouveau**, Rejeter / Appliquer à la fiche + trace) — badge « email vérifié (code) » en Phase 2.

**Liste des formulaires**
- [x] **M7 — Cartes révisées** (réabsorbe F1) : **badges de type de bloc** ; **4 actions en ICÔNES** + tooltips (✎ Modifier · 📥 Réponses · 👁 Aperçu · 🔗 Lien) ; **compteur réponses gardé en méta** ; **pastille « À valider · N »** si modifs en attente ; **toolbar** (recherche nom/desc + filtre Statut + filtre Type + **tri par dropdown** : Nom/Création/Réponses/Validité) ; **pagination client** (~15/page, en filet). Archivés = section repliable (déjà là).

**Public + sécurité**
- [x] **M8 — Page publique multi-blocs** + Aperçu admin : rendu listes + sondage ; bloc fiche en **write-only** (Phase 1) → crée des `FieldProposal` (pending), **sans OTP**. Sanitisation en sortie.
- [x] **M9 (Phase 2) — OTP + pré-remplissage** : **gate complet** dès qu'un bloc `fiche` est présent. Flux 2 temps (ouverture → code envoyé à l'email masqué → saisie → session courte 20 min → page complète **pré-remplie**). `FormAccessCode` (hash scrypt, jamais le code clair) + TTL 10 min + cooldown 60 s (anti-flood) + 5 essais max ; renvoi de code manuel. Propositions marquées `otp_verified` → **badge « ✅ email vérifié »** dans « À valider ». Migration `tools/migrate_add_form_access_code.py` (appliquée en dev). ⚠️ **à lancer sur prod (lfll) au déploiement.**
  - **Hygiène table OTP** (sans planificateur) : purge opportuniste à chaque envoi (≤ 1 code par contact/formulaire + balayage global des codes oubliés > 24 h) ; **cascade** à la suppression d'un formulaire (efface `form_access_code` + `field_proposal` — sans relationship cascade, sinon orphelins). Codes morts déjà inertes (vérif exige `consumed=False AND expires_at>now`) → purge = minimisation RGPD + table bornée.

**⚠️ Transverse (dès qu'un contact écrit)** : échappement à TOUS les points de sortie (mailer HTML, export TSV `= + - @`, vCard, admin) ; CSRF (Flask-WTF) sur POST publics + session OTP.

**❓ QUESTION DE CONCEPTION — granularité de validation (à trancher, #23-2)** :
Aujourd'hui l'onglet « À valider » applique/rejette **par contact** (globalement : tous les champs proposés par un contact d'un coup).
- **Listes** : appliquées **directement** sur la page publique (choix d'abonnement du contact = self-service, faible risque) → *proposition : garder l'application directe, pas de validation* (à confirmer — sinon on ferait aussi transiter les listes par la file).
- **Champs de fiche** : options de granularité →
  - *globale par contact* (actuel) : simple, mais on ne peut pas accepter le tél. et refuser l'adresse ;
  - *par sélection* : cases à cocher pour choisir les champs à appliquer, puis 1 bouton ;
  - *individuelle par champ* : Accepter/Refuser sur **chaque** diff — le plus fin, plus de clics.
- **Piste retenue à valider** : **individuelle par champ** (Accepter ✓ / Refuser ✗ sur chaque ligne de diff) **+** un « tout appliquer / tout rejeter » de repli sur la carte contact → couvre les deux besoins. Contexte associatif/sensible = mieux vaut pouvoir trier finement.
- Impact technique : `proposal_apply`/`proposal_reject` doivent accepter un **id de FieldProposal** (pas seulement `contact_id`) ; statut par proposition (déjà le cas — chaque `FieldProposal` a son `status`).

### 🧪 Retours test prod v2.0.0-rc1/rc2 (2026-07-29 → 08-04)
- ✅ **Test 1** : mailing avec OTP + formulaire aux 3 blocs (listes/sondage/fiche) → **tout fonctionne en conditions réelles**.
- [x] **🐛 Dédup des propositions** — re-soumettre ne crée plus de doublons dans « À valider » : upsert `pending` par (form, contact, champ), retour à la valeur canonique = proposition retirée. **Fait (lot F, 08-04).**
- [x] **`is_test` (Bug #2)** — un « Envoi un test » suit le parcours réel (OTP compris) mais sa donnée est taguée `is_test` et **exclue partout** (verrou, compteurs, Réponses, À valider, export) → tester un formulaire ne le verrouille/pollue plus. Marqueur `?test=1` injecté dans le lien du seul exemplaire test, propagé de bout en bout ; isolation test/réel. **Fait (lot F, 08-04).** ⚠️ migration `migrate_add_form_is_test.py` à lancer au déploiement.
- [x] **Compteur « À valider » par contact** (fiches à traiter) au lieu du total de champs. **Fait (lot F, 08-04).**
- [ ] **« Revoir mes choix » (page de confirmation) — round-trip incohérent** *(reporté : discussion béta/alpha, décision user 08-04)* :
  - Le lien rouvre le formulaire public. **Listes** re-cochées (appliquées en direct) ✓ ; **sondage** NON réaffiché (stockage isolé) ; **fiche** pré-remplie avec les valeurs **canoniques**, pas la proposition en attente.
  - **Décision à prendre** : **(a)** confirmation terminale (retirer/requalifier « Revoir mes choix ») ; ou **(b)** retour honnête → pré-remplir le sondage depuis `PreferenceResponse.data`, afficher la fiche « proposé : X (en attente) ». (Dédup déjà faite.)
- [ ] **Fenêtre de ré-édition & intégrité des choix (discussion 29/07)** — bien distinguer :
  - **OTP = identité** (session ~20 min pour ne pas re-vérifier à chaque micro-changement) ≠ **limitation des ré-éditions** (contrôle séparé). L'OTP n'empêche pas de re-modifier (l'usager redemande un code sur sa propre boîte).
  - Le risque « revoter/modifier à l'infini, remettre en cause une décision » se traite par : **clôture** (déjà obligatoire si bloc fiche) + **sémantique du sondage** à décider — réponse **figée après 1ʳᵉ soumission** (vote) *vs* **modifiable jusqu'à clôture** (préférences), option par bloc/formulaire. La **fiche** reste ré-éditable (donnée perso) → juste **dédupliquer**.
  - **Proposition A (à confirmer)** : après expiration de session, **ne plus auto-renvoyer** le code — clic explicite « Recevoir un code » sur le gate (moins d'emails auto, ré-entrée délibérée).
  - **Proposition B** : dans « À valider », afficher mais rendre **non validable pendant un délai de décantation** (≈ `proposed_at + 20 min`) → ne pas valider une valeur encore modifiable ; à coupler avec la **déduplication (upsert)**. Alternative simple : dédup + valider la dernière version.

**Phasage** :
- **Phase 1 (MVP livrable)** = M1(sans OTP) → M2 → M3 → M4 → M5 → M6(sans badge OTP) → M7 → M8(write-only). Assembleur complet + sondage + file de validation + liste enrichie, **sans OTP/pré-remplissage**.
- **Phase 2** = M9 (OTP + pré-remplissage) + badge email-vérifié.
- [x] **G. Demandes de diffusion** — refonte de l'écran **Fait (08-04)** : aperçu du contenu **inline** (👁 / clic sujet), **PJ soignées** (nom tronqué + taille o/Ko/Mo, date compacte), **vue des archivées** (`?archived=1`, dossier IMAP « Traité »), actions en icônes + « Utiliser » en bouton, polish (`<style>` sorti). *(Reste : la **notification** aux users à réception d'une demande = follow-up backend séparé — nécessite un scan périodique, cf. « Notification des demandes de diffusion » plus haut.)*
- [x] **H. Paramètres — contenu** — **Fait (08-04)** : section **« Envoi (SMTP) »** + **bouton « Tester la connexion »** (AJAX, ✓/✗) ; section **« Valeurs par défaut »** (éditeur des civilités → `choices.civilite`) ; section **« Gestion du bounce »** toggle ON/OFF (`bounce_enabled` ; OFF = pas de Return-Path bounce → règle le 553). *(Reste optionnel : convertir `titre` en select éditable ; « Expéditeur » éditable en UI plutôt que `.env` ; onglets horizontaux du design CLD au lieu de la sous-nav sidebar.)*

### 🔭 PHASE 2 — EPIC « Sélection & Segments » (ciblage/gestion des contacts, retours béta) — EN COURS
**Design validé (08-04)** — v. la discussion socle :
- **Sélection courante = objet DÉDIÉ** (pas de réutilisation de `Liste` : éviter l'erreur de catégorie transitoire/durable + la taxe « exclure is_temporary partout »). Forme légère **`selection_member(user_id, contact_id)`** (singleton par user), set-algebra en SQL pur, portable. « Enregistrer comme liste » = copie vers une vraie `Liste` (`created_by_id` → futur « mes listes »). Évolutif : entête `Selection(id,user,name)` si sélections nommées un jour.
- **Filtres = ad-hoc** (calculés à la volée) pour commencer ; segments nommés plus tard.
- **« Pas répondu au formulaire X » v1** = *base choisie ∖ répondants(form)* (différence ensembliste) ; ciblage auto « qui a reçu ce form » = plus tard.

**Staging :**
- [x] **S1 — Journal `ContactSend(contact_id, campaign_id, sent_at)`** + backfill + écriture dans `_run_send`. Débloque « jamais mailé » / « déjà reçu campagne X » / histo contact. **Fait (08-04).** ⚠️ migration `migrate_add_contact_send.py` au prochain déploiement.
- [x] **S2 — Sélection courante** (`selection_member`, singleton/user) + **chip transverse** (Voir · Envoyer un mailing · Enregistrer comme liste · Vider) + → sélection / vider.
- [x] **S3 — Filtres dynamiques Contacts** : dates (`created_at`), membre/non-membre liste, **répondu/pas-répondu formulaire**, jamais-mailé, désabonnés/bounces (déjà partiels) → chacun alimente la sélection.
- [x] **S4 — Opérations ensemblistes** sur la sélection (Ajouter ∪ / Retirer ∖ / Intersecter ∩ / Remplacer).
- [x] **S5 — Mailing** : cibler la **sélection courante** + option **exclure « déjà reçu »** (via `ContactSend`).
- Relié : « segments dynamiques » (bounces/jamais-mailés/désabonnés) + « Modèles » (Tier 2) + « Réutiliser → nouvelle campagne » (à traiter avec les Modèles). À distinguer de la nav Précédent/Suivant fiche (client, éphémère).

**Composants / UX transverses :**
- [x] **Modale de confirmation réutilisable et unique** (remplacer les `confirm()` natifs : corbeille contacts, suppression utilisateur, suppression campagne…)
- [ ] **Assistant variables** dans l'éditeur mailing + gestion propre de l'absence de **civilité** (éviter « Bonjour ,  Nom »)
- [ ] Polish shell : icônes dans la sidebar, en-tête sticky

**Contacts / données :**
- [ ] **Recherche étendue** : au-delà de nom/prénom/email → ex. « contacts sans téléphone », recherche dans les **champs personnalisés**
- [ ] **(Dés)abonnement — traçabilité complète** : modale avec champ **« Raisons »** + colonne dédiée **`unsubscribed_by_id`** (aujourd'hui l'acteur est tracé via `updated_by_id`)
- [ ] **Corbeille en mode user** : accès en **restauration seule**, via modale, **filtré sur les mises en corbeille du `current_user`**
- [ ] Fiche contact : filet défensif d'affichage/import (valeurs `"None"`/`"nan"` → champ vide)

**Listes :**
- [ ] **Mobile** : le chapeau de 3 tuiles stats (Listes actives / Contacts / Abonnés joignables) prend trop de place → compacter / masquer / accordéon

**Mailing :**
- [ ] **Templates génériques** (email de bienvenue, de désabonnement, etc.) : aujourd'hui « enregistrer le brouillon » puis l'utiliser **détruit** le brouillon → concevoir une vraie notion de modèle réutilisable
- [x][ ] **Sous-menu « Modèles »** (dans la sous-nav Mailing) listant les campagnes-modèles enregistrées. Actions : **Voir / Utiliser / Archiver / Supprimer (admin)**. « Utiliser » **duplique** le modèle vers une **nouvelle campagne** (sujet, corps, PJ, listes) — le modèle n'est **jamais** modifié ni consommé.
  - [ ][ ] **Archi** : flag **`is_template`** sur `MailCampaign` (+ migration) ; un modèle n'est jamais envoyé ; « Utiliser » = clone via la logique de persistance existante. Réutilise le pattern **archivage réversible + suppression admin depuis les archives** (comme Listes / Formulaires).
  - [ ][ ] **Listes copiées = valeurs par défaut pré-cochées, PAS un verrou** → modifiables à l'étape Destinataires (la cible varie souvent, ex. email de bienvenue).
  - [ ][ ] **Pièces jointes dupliquées physiquement** (copie dans le dossier de la nouvelle campagne) → la PJ de l'instance est indépendante de celle du modèle.
  - [ ][ ] Bouton **« Enregistrer comme modèle »** (promotion d'un brouillon). Distinction claire : **brouillon** = à envoyer une fois ↔ **modèle** = réutilisable N fois.
  - [x] Entrée de sous-nav **« Modèles »** posée (inactive, badge « bientôt ») — 27/07, pour visibilité roadmap (meeting).

**Accueil / Dashboard (idée #20) :**
- [ ] **Landing page d'accueil** (après login) : tableau de bord avec stats + **mise en exergue de ce qui demande attention** — erreurs d'envoi, bounces (quand traités), demandes de diffusion en attente, etc. Deviendra la vraie « vue neutre » d'accueil (le clic « Mailing » reste sur Historique en attendant).

**Identité / signature de l'app (v2, idée 2026-07-27) :**
- [x] **Page « À propos »** (`/a-propos`) : présentation des fonctions + paramétrages + **crédits** (« Conçu par Nicolas Farrié, développé par Nicolas Farrié & Claude »). Accès : rendre **cliquable la ligne de version** en pied de sidebar + lien depuis Paramètres → Généraux + **signature discrète en pied de la page de connexion**. **Texte de base prêt** : `doc-travail/a-propos-brouillon.md`. (Graine de la future landing page + de la doc utilisateur.)
- [ ] **Page de connexion — texte de présentation éditable par la structure** : un champ (Setting, éditable dans **Paramètres → Généraux**) où l'association saisit quelques lignes de présentation, **affichées sur le login** (à côté / sous le formulaire). Complète l'apparence login déjà personnalisable (image de fond + voile). 
      



