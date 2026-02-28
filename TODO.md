# Contact Mailer - TODO

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
- [x] Bulk actions disponibles sur mobile : checkboxes sur les cards, barre toggle "Actions ▾"
- [x] Code couleur boutons : bleu création, orange modification, vert foncé action/filtre, rouge suppression
- [x] Filtre contacts : réorganisation (liste → source → recherche → bouton), source réservée aux admins
- [x] Favicon SVG (onglet navigateur + icône mobile)

## Correction Bug ou pb interface - Prioritaire
- [x] Problème de cohérence entre les dénominations de champ, dans la base, à l'import, et en affichage (ex listes | catégories | groups)
- [x] Liste des messages déjà envoyés, réutilisation pour nouvel envoi

## A faire - Prioritaire
- [x] Gestion multi-utilisateurs : CRUD users, rôles admin/user, qui a fait quoi
- [x] Déploiement multi-instance : middleware ReverseProxied, templates systemd/nginx, script create_instance.sh, landing page
- [x] Mot de passe oublié : notification admin par email (sans tokens)
- [x] Intégration API BookStack : sync rôles, push contacts avec rôle, invitation optionnelle, langue fr par défaut
- [ ] Import interactif : page de revue des doublons avec choix par contact (ignorer/remplacer listes/fusionner listes) + option "pour tous"
- [ ] Support templates .eml (brouillons Thunderbird) - format standard RFC 5322

## A faire - Améliorations
- [x] Export vCard (réutiliser vcard_converter.py en sens inverse)
- [~] Historique des campagnes envoyées (historique messages, envois // reste à faire : historique par contact)
- [x] Spinner overlay "Envoi en cours" sur le bouton de lancement de campagne
- [x] Pièces jointes dans les mailings (upload, stockage, envoi MIMEBase)
- [x] Affichage du message dans la file d'attente : toggle afficher/masquer, rendu HTML via iframe
- [ ] Envoi asynchrone (ne pas bloquer l'interface pendant l'envoi)
- [ ] Pagination de la liste des contacts
- [ ] Recherche avancée (filtres multiples)
- [ ] Fusionner deux listes
