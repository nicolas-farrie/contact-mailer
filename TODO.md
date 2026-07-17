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

## A faire - Améliorations
- [x] Export vCard (réutiliser vcard_converter.py en sens inverse)
- [~] Historique des campagnes envoyées (historique messages, envois // reste à faire : historique par contact)
- [x] Spinner overlay "Envoi en cours" sur le bouton de lancement de campagne
- [x] Pièces jointes dans les mailings (upload, stockage, envoi MIMEBase)
- [x] Affichage du message dans la file d'attente : toggle afficher/masquer, rendu HTML via iframe
- [~] Historique mailing : affichage du détail d'une campagne (corps du mail, liste, pièces jointes) — clic sur ligne ou bouton dédié
- [ ] Envoi asynchrone (ne pas bloquer l'interface pendant l'envoi)
- [ ] Pagination de la liste des contacts
- [ ] Recherche avancée (filtres multiples)
- [ ] Fusionner deux listes
- [~] Export vCard : route disponible (3.0/4.0), compatibilité Thunderbird à investiguer

## Session debug 2026-07 (régressions post-restructuration blueprints)
- [ ] Bouton « Envoyer un email de test » : câbler la route POST /mailing/test-smtp (existe déjà) dans la page **Paramètres** — page à renommer **« Généraux »**
- [ ] Régler le bloqueur bounce 553 (MAIL FROM=bounce@ rejeté par le SMTP) — décision config/infra
- [ ] Test exhaustif bouton par bouton : Mailing (M1–M18) puis Formulaires (F1–F11)
- [ ] Éditeur mailing : vérifier la version de l'éditeur utilisée ; passer l'UI/commandes en français (actuellement en anglais) ; ajouter un bouton « insérer une image » (seul Ctrl+V/Ctrl+C fonctionne)
- [ ] Bouton « Envoyer X emails maintenant » : feedback visuel selon le résultat — échec → rouge + texte « Recommencer… » / « Afficher le log de l'envoi » ; succès → vert + texte différent de celui d'avant l'envoi
- [ ] File d'envoi — état « terminé » : afficher un état de succès explicite (vert, « ✓ Campagne envoyée ») au lieu de l'actuel bouton contextuel
- [ ] File d'envoi — DANGER UX : quand tout est envoyé, l'emplacement affiche « Supprimer la campagne » (`mailing_queue.html:81`), qui appelle `delete_campaign` → **efface aussi l'historique** (queue + template), pas seulement la file. Remplacer par un simple bouton **« Retour »** vers l'accueil Mailing (prudence : un utilisateur ne doit pas supprimer sans en connaître les conséquences)
- [x] BUG : après envoi, item reste « En attente » — cause = ids non uniques (len()+1 recyclé après suppression de campagnes) → mark_sent/mark_error frappent le mauvais item. Corrigé (id=max+1) + outil tools/fix_queue_ids.py pour les fichiers existants
- [ ] Demandes de diffusion — liste : pouvoir prévisualiser le CONTENU du mail (corps + PJ) directement depuis la liste, AVANT « Utiliser pour un mailing »
- [ ] Demandes de diffusion — traçabilité expéditeur : conserver l'adresse du demandeur (en pied de mail / métadonnée) pour lui renvoyer un compte-rendu d'exécution du mailing (qui a validé + infos du mailing envoyé)
- [ ] Demandes de diffusion — UX pièces jointes : la PJ d'une demande n'apparaît PAS dans le champ habituel des pièces jointes, mais comme case « Ajouter à l'envoi » décochée dans l'encart bleu (mailing.html:37) → trop facile à manquer, on envoie sans la PJ. À rendre évident (pré-cocher ? remonter dans la zone PJ standard ? avertir si non cochée à l'envoi)
- [ ] Demandes de diffusion — archivées invisibles : le bouton « Archiver » déplace vers le dossier IMAP `Traite`, mais AUCUNE vue in-app ne permet de consulter les demandes archivées (submissions() ne scanne que INBOX). Ajouter un affichage des demandes archivées
- [x] BUG lien formulaire cassé dans l'email (http://p/... NXDOMAIN) : TinyMCE relativisait les URLs same-domain (convert_urls défaut=true). Corrigé dans mailing.html (convert_urls/relative_urls/remove_script_host = false). NB : ne se manifestait que quand domaine du lien == domaine de l'app (cas prod). À redéployer (v1.2.12) pour lfll.
- [ ] Formulaire — page de confirmation (« Préférences enregistrées ») : ajouter un bouton « Revoir mes choix » (ou une note « vous pouvez rouvrir la page de vos choix depuis le lien reçu par email »)
- [ ] Formulaire — sécurité du lien public : token + uid permanents, pas d'expiration par lien → un formulaire sans date de clôture = lien bearer permanent (consultation/modif des abonnements du contact ad vitam). Suggérer/imposer une date de clôture ; envisager expiration/rotation du lien. Cf. [[formulaires-next-subjects]]
- [ ] Formulaire (édition/création) : le formulaire est contraint sur une demi-page ; l'étendre sur toute la largeur disponible (moins les marges esthétiques)
- [ ] Documentation utilisateur : rédiger une vraie doc par fonction (menus Mailing, Formulaires, Contacts, Listes, Paramètres… chaque bouton/action), destinée aux utilisateurs finaux des petites structures
- [ ] Paramètres : ajouter une case à cocher « Gestion du Bounce » (activer/désactiver). Sur les petites structures (cœur de cible de l'app), le suivi des bounces n'est pas indispensable → permettre de le désactiver proprement dans l'UI, au lieu de bidouiller les variables .env (quand OFF : pas d'adresse bounce forcée en enveloppe → règle aussi le rejet SMTP 553)


