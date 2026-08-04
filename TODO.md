# Contact Mailer - TODO
# le [ ] vide indique non fait ; le [x] fait ; le [~] partiellement fait ; le [?] pas sûr qu'il faille le faire (à rediscuter)
# - [ ][ ] - sous point
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

- [x] **🔴 Mailing : séquence d'envoi phase 3 → phase 4 — CORRIGÉ (08-04, Tier 0)**. La confirmation de l'étape Destinataires **déclenche réellement l'envoi** : `add_to_queue` met en file **puis** `_run_send()` (envoi immédiat) → on arrive en phase Envoi sur un **état résultat**. `process()` devient « Reprendre l'envoi » (file d'attente, cas interrompu/erreurs). Modale unique « Envoyer maintenant » + overlay. Prépare l'asynchrone (confirmer = file + armer le déclencheur). *(Fini le « resté en file, jamais parti ».)*

## A faire - Prioritaire
### Formulaires — 2 gros sujets liés (analyse cadrée le 6/07, à traiter ensemble, sécurité intégrée dès la conception)
- [ ] Champs de la base éditables dans le formulaire (self-service auto-correction)
- [ ][ ] Liste blanche de champs éditables par formulaire (comme la sélection des listes → table type PreferenceFormField ou colonne JSON)
- [ ][ ] Page publique : pré-remplissage des valeurs, édition, update du contact ; email/uid exclus par défaut (identité + dedup import) ; traçabilité "modifié par le contact"
- [ ] Sécuriser l'accès quand des champs sont exposés (le lien est une "capability URL" : token 128 bits + expiry, HTTPS ; risque = fuite du lien)
- [ ][ ] Option retenue à décider : (préféré) proposition→validation admin — supprime la surface d'injection ; ou OTP e-mail ; ou confirmer un champ connu ; ou SMS OTP (option forte, mais coût provider + numéros mobiles peu fiables)
- [ ][ ] ⚠️ Auth ≠ sanitisation : échapper/sanitiser les champs contact partout où ils ressortent NON échappés — mailer replace_vars (HTML des mails), export CSV/TSV (formula injection Excel), export vCard
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

## A faire - Améliorations
- [x] Export vCard (réutiliser vcard_converter.py en sens inverse)
- [~] Historique des campagnes envoyées (historique messages, envois // reste à faire : historique par contact)
- [x] Spinner overlay "Envoi en cours" sur le bouton de lancement de campagne
- [x] Pièces jointes dans les mailings (upload, stockage, envoi MIMEBase)
- [x] Affichage du message dans la file d'attente : toggle afficher/masquer, rendu HTML via iframe
- [~] Historique mailing : affichage du détail d'une campagne (corps du mail, liste, pièces jointes) — clic sur ligne ou bouton dédié
- [ ] Envoi asynchrone (ne pas bloquer l'interface pendant l'envoi)
- [x] Pagination de la liste des contacts (Lot A refonte : pagination client 25/page, sélection conservée entre pages)
- [x] Cache-busting des assets statiques (fait : ?v=mtime via global Jinja asset_version) (`?v={{ config.APP_VERSION }}` sur style.css / JS) — évite que le navigateur serve un ancien CSS après déploiement (piège rencontré en test refonte : Ctrl+Shift+R nécessaire)
- [~] **Segments dynamiques accessibles à l'utilisateur** (décision 22/07 ; **PARTIEL** : filtre Statut Abonnés/Désabonnés/Bounces ajouté en Lot A — reste « jamais mailés » + corbeille comme vues) : donner accès depuis la page Contacts
  aux sélections calculées — **désabonnés**, **bounces** (`has_bounced`), **jamais mailés**, corbeille — sous forme de
  filtres/vues. Aujourd'hui la page Contacts ne filtre que par liste / source / recherche → impossible de voir les
  désabonnés. Les listes restent l'outil end-user "curé" ; les segments sont l'outil dynamique, mais ils doivent être
  **manipulables par l'utilisateur**, pas seulement internes. (Version ultérieure, validé.)
- [ ] Recherche avancée (filtres multiples)
- [ ] Fusionner deux listes
- [ ] **Stats de formulaires (ouverts / répondus)** — la seule métrique « ouverture/clic » qui a du sens en non-marchand, et quasi gratuite : le clic atterrit chez nous. GET page publique = **ouvert**, POST = **répondu**. Compter/afficher par formulaire (taux de réponse). Pas de tracker externe, pas de pixel — respectueux.
- [ ] **Garde-fou volume d'envoi** — le vrai plafond = quota du serveur mail (`mail.aubaygues.fr`), pas la réputation (base 100 % opt-in). Ajouter : **cap quotidien configurable** + **avertissement au-delà d'un seuil** (ex. > 500 en un envoi) + conseil de **montée en charge progressive** (warm-up). Le pacing existe déjà (`MAIL_RATE_PER_MINUTE=20` → 3 s/email) + file d'attente. Pré-requis délivrabilité à vérifier : **SPF/DKIM/DMARC** sur aubaygues.fr. **📄 Mémo complet : `doc-travail/delivrabilite-envoi.md`.**
- [ ] **⚙️ ACTION — demander à l'admin de `mail.aubaygues.fr` ses quotas d'envoi** (par heure / par jour) → c'est le plafond dur qui conditionne la taille des envois. **+ vérifier SPF/DKIM/DMARC** sur `aubaygues.fr` avant tout envoi élargi. Cf. `doc-travail/delivrabilite-envoi.md`.
- [~] Export vCard : route disponible (3.0/4.0), compatibilité Thunderbird à investiguer

## RGPD / données personnelles (à traiter avec soin)
- [ ] **Suppression d'un utilisateur — stratégie RGPD** (actuellement `users.delete` = hard delete sec). Constat : `MailCampaign.sent_by` est un snapshot texte (historique campagnes SAIN, non impacté) ; mais `Contact.created_by_id/updated_by_id/deleted_by_id` + `PreferenceForm.created_by_id` sont des FK vers user → sur SQLite (FK non appliquées) le delete laisse des refs orphelines (lectures gardées → « — », pas de crash) ; **planterait** si FK activées / Postgres (pas de try/except). 
  - **Préférence retenue (à discuter au moment du traitement)** : plutôt **nullation** des refs OU **obfuscation destructive** des données signifiantes de l'utilisateur, en **laissant les historiques consultables** (plus simple à gérer que tout supprimer). Privilégier la **désactivation** (déjà là) comme geste normal ; la suppression = purge exceptionnelle (droit à l'effacement).
  - Fix technique associé : nuller les refs + try/except à la suppression ; à terme `PRAGMA foreign_keys=ON` + `ondelete='SET NULL'`. Doit être **carré** côté conformité.
- [ ] Vérifier plus largement les autres surfaces RGPD (export/effacement des données d'un contact, consentement formulaires, rétention).

## Robustesse du service (analyse 2026-07-18)
- [x] File d'envoi migrée du fichier JSON vers la DB (tables mail_campaign / mail_queue_item, colonnes JSON pour snapshot contact + PJ). Écritures transactionnelles, ids auto-incrémentés (fin des collisions), sauvegardé avec la DB. Interface MailQueue inchangée. Migration : tools/migrate_queue_to_db.py. (tools/fix_queue_ids.py devient obsolète.)
- [ ] Timeout IMAP dans le chemin des requêtes (`IMAP4_SSL(..., timeout=10)`) — évite le gel d'un worker si le serveur mail ne répond pas
- [ ] Ajouter la protection CSRF (Flask-WTF) sur les formulaires POST
- [ ] Fork-safety : `init_db()`/`db.engine.dispose()` en post_fork (gunicorn --preload) ; assert SECRET_KEY ≠ défaut en prod
- [ ] (Confort) WAL SQLite, pages d'erreur 404/500 personnalisées, envoi asynchrone si les listes grossissent
- [ ] **Portabilité moteur DB — SQLite → Postgres (audit 2026-07-27)** : couche d'accès **saine** (100 % ORM, aucun SQL brut, URI **env-driven** `SQLALCHEMY_DATABASE_URI`, `.ilike`/`db.JSON` portables ; un Postgres **neuf** marche via `db.create_all()`). **Bascule = coût faible et borné, pas de réécriture.** 2 chantiers à traiter le jour où on bascule :
  - [ ] **Migrations → Alembic / Flask-Migrate** : les ~10 `tools/migrate_*.py` sont en **`sqlite3` brut + PRAGMA** → non portables. Converger vers Alembic (engine-agnostic) ; ne concerne que l'évolution in-place (pas un déploiement neuf). Cf. [[deploy-and-migrations-cleanup]].
  - [ ] **Fiabiliser les hard-deletes (contraintes FK)** : SQLite n'applique pas les FK, **Postgres oui** → `users.delete` (+ `FieldProposal`, refs `*_by_id` de Contact/PreferenceForm) lèverait une **violation FK**. Nuller les refs / `ondelete='SET NULL'` + activer `PRAGMA foreign_keys=ON` en dev pour dé-risquer tôt. **Recoupe l'item RGPD** (suppression utilisateur). Les relations en `cascade='all, delete-orphan'` sont déjà propres.
  - [ ] Ops bascule : ajouter `psycopg2`, service Postgres, ETL one-shot des données (ex. `pgloader`).

## Session debug 2026-07 (régressions post-restructuration blueprints)
- [~] Bouton « Envoyer un email de test » : câbler la route POST /mailing/test-smtp (existe déjà) dans la page **Généraux** — *renommage « Paramètres »→« Généraux » **FAIT** 26/07 ; reste à câbler le bouton*
- [x] Régler le bloqueur bounce 553 (MAIL FROM=bounce@ rejeté par le SMTP) — fait 26/07 : fonction bounce **retirée du `.env`** (BOUNCE_RETURN_PATH/IMAP vidés) → enveloppe = compte SMTP authentifié. **À répliquer en prod lfll.** (Le toggle UI « Gestion du Bounce » reste à faire, voir plus bas.)
- [ ] Test exhaustif bouton par bouton : Mailing (M1–M18) puis Formulaires (F1–F11)
- [ ] Mailing/P2 — gestion de l'absence de Civilité : la civilité reste optionnelle (respect / non-binaire), donc `{civilite}` peut être vide → l'assistant variables (P2) doit aider à gérer l'absence proprement (ex. `{civilite:{civilite} :}` conditionnel, ou salutation neutre par défaut) pour éviter les « Bonjour ,  Nom » disgracieux. (L'accord de genre, lui, est réglé : « Inclusif » par défaut, jamais vide.)
- [ ] Éditeur mailing : passer l'UI/commandes en français ; ajouter un bouton « insérer une image » (seul Ctrl+V/Ctrl+C fonctionne)
  - EN ATTENTE de la proposition UI de Claude Design avant de trancher l'éditeur. Faits établis (2026-07-18) : version actuelle **TinyMCE 6.8.5**, dernière **8.8.0**. Depuis la v7, auto-hébergement en GPLv2+ exige `license_key: 'gpl'` (gratuit) ; en **v8, sans clé l'éditeur passe en lecture seule**. Options : garder 6.8.5 (OK, aucune clé) / upgrade 8.8.0 + `license_key:'gpl'` / remplacer par TipTap ou Unlayer (builder email, merge-tags cliquables). Ne pas migrer avant de savoir si on garde TinyMCE.
- [ ] Bouton « Envoyer X emails maintenant » : feedback visuel selon le résultat — échec → rouge + texte « Recommencer… » / « Afficher le log de l'envoi » ; succès → vert + texte différent de celui d'avant l'envoi
- [x] File d'envoi — état « terminé » : alerte de succès verte « ✓ Campagne envoyée » (mailing_queue.html)
- [x] File d'envoi — DANGER UX : bouton « Supprimer la campagne » remplacé par « ← Retour aux mailings » (vers mailing.history). Suppression toujours possible depuis l'historique
- [x] BUG : après envoi, item reste « En attente » — cause = ids non uniques (len()+1 recyclé après suppression de campagnes) → mark_sent/mark_error frappent le mauvais item. Corrigé (id=max+1) + outil tools/fix_queue_ids.py pour les fichiers existants
- [ ] Demandes de diffusion — liste : pouvoir prévisualiser le CONTENU du mail (corps + PJ) directement depuis la liste, AVANT « Utiliser pour un mailing »
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
- [ ] Paramètres : ajouter une case à cocher « Gestion du Bounce » (activer/désactiver). Sur les petites structures (cœur de cible de l'app), le suivi des bounces n'est pas indispensable → permettre de le désactiver proprement dans l'UI, au lieu de bidouiller les variables .env (quand OFF : pas d'adresse bounce forcée en enveloppe → règle aussi le rejet SMTP 553)
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

### 🔭 Révision fonctionnelle par bloc — PHASE 2 (À OUVRIR APRÈS la finition de la spec CLD, cf. [[refonte-v2-phasage]])
Fonctions issues du béta-test, jugées **indispensables à l'utilisabilité** (à concevoir à froid) :
- [ ] **Contacts — filtres personnalisés** : au-delà des filtres auto (Statut/Liste/Source), des filtres définis par l'utilisateur (combinaisons, « sans téléphone », champs perso…).
- [ ] **Listes — opérations ensemblistes** : union (∪), intersection (∩), différence, complément entre listes/sélections.
- [ ] **⭐ Sélection courante / liste temporaire = OUTIL TRANSVERSE (insight user 08-04)** : matérialiser une sélection ou un résultat de filtre en un **objet manipulable**, **partagé et accessible d'un bloc fonctionnel à l'autre** (Contacts → Mailing → Formulaires…), pas un état par écran.
  - **Implication d'archi** : doit vivre **côté serveur** pour être consommable par les autres blocs (Mailing envoie à la sélection courante, etc.) → **session serveur** (petites sélections) ou **objet DB par utilisateur** (`selection courante`, promue en vraie `Liste` à la demande ; survit au refresh ; volumes importants). PAS uniquement du `sessionStorage` client.
  - **À distinguer** de la séquence Précédent/Suivant de la fiche (Lot C) : celle-ci est **client, éphémère, navigation seule** (`sessionStorage.contactNavSeq`) — un cas d'usage étroit, pas l'outil transverse.
  - Relié aux « segments dynamiques » (bounces / jamais-mailés / désabonnés) déjà pointés comme futurs **filtres/vues** côté Contacts.

**Composants / UX transverses :**
- [ ] **Modale de confirmation réutilisable et unique** (remplacer les `confirm()` natifs : corbeille contacts, suppression utilisateur, suppression campagne…)
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
- [ ][ ] **Sous-menu « Modèles »** (dans la sous-nav Mailing) listant les campagnes-modèles enregistrées. Actions : **Voir / Utiliser / Archiver / Supprimer (admin)**. « Utiliser » **duplique** le modèle vers une **nouvelle campagne** (sujet, corps, PJ, listes) — le modèle n'est **jamais** modifié ni consommé.
  - [ ][ ] **Archi** : flag **`is_template`** sur `MailCampaign` (+ migration) ; un modèle n'est jamais envoyé ; « Utiliser » = clone via la logique de persistance existante. Réutilise le pattern **archivage réversible + suppression admin depuis les archives** (comme Listes / Formulaires).
  - [ ][ ] **Listes copiées = valeurs par défaut pré-cochées, PAS un verrou** → modifiables à l'étape Destinataires (la cible varie souvent, ex. email de bienvenue).
  - [ ][ ] **Pièces jointes dupliquées physiquement** (copie dans le dossier de la nouvelle campagne) → la PJ de l'instance est indépendante de celle du modèle.
  - [ ][ ] Bouton **« Enregistrer comme modèle »** (promotion d'un brouillon). Distinction claire : **brouillon** = à envoyer une fois ↔ **modèle** = réutilisable N fois.
  - [x] Entrée de sous-nav **« Modèles »** posée (inactive, badge « bientôt ») — 27/07, pour visibilité roadmap (meeting).

**Accueil / Dashboard (idée #20) :**
- [ ] **Landing page d'accueil** (après login) : tableau de bord avec stats + **mise en exergue de ce qui demande attention** — erreurs d'envoi, bounces (quand traités), demandes de diffusion en attente, etc. Deviendra la vraie « vue neutre » d'accueil (le clic « Mailing » reste sur Historique en attendant).

**Identité / signature de l'app (v2, idée 2026-07-27) :**
- [ ] **Page « À propos »** (`/a-propos`) : présentation des fonctions + paramétrages + **crédits** (« Conçu par Nicolas Farrié, développé par Nicolas Farrié & Claude »). Accès : rendre **cliquable la ligne de version** en pied de sidebar + lien depuis Paramètres → Généraux + **signature discrète en pied de la page de connexion**. **Texte de base prêt** : `doc-travail/a-propos-brouillon.md`. (Graine de la future landing page + de la doc utilisateur.)
- [ ] **Page de connexion — texte de présentation éditable par la structure** : un champ (Setting, éditable dans **Paramètres → Généraux**) où l'association saisit quelques lignes de présentation, **affichées sur le login** (à côté / sous le formulaire). Complète l'apparence login déjà personnalisable (image de fond + voile). 
      



