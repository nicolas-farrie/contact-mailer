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

## A faire - Prioritaire
- [ ] Import interactif : page de revue des doublons avec choix par contact (ignorer/remplacer listes/fusionner listes) + option "pour tous"
- [ ] Gestion des désabonnements (obligatoire légalement : lien de désinscription dans chaque mail)
- [ ] Support templates .eml (brouillons Thunderbird) - format standard RFC 5322

## A faire - Déploiement
- [ ] Configuration Nginx (reverse proxy)
- [ ] Sécurisation : SECRET_KEY, mot de passe admin, HTTPS
- [ ] Service systemd pour l'exécution en production (gunicorn)

## A faire - Améliorations
- [ ] Export vCard (réutiliser vcard_converter.py en sens inverse)
- [ ] Historique des campagnes envoyées
- [ ] Envoi asynchrone (ne pas bloquer l'interface pendant l'envoi)
- [ ] Pagination de la liste des contacts
- [ ] Recherche avancée (filtres multiples)
- [ ] Fusionner deux listes