# Contexte de synchronisation — Contact Mailer (juillet 2026)

> À fournir à Claude Design en tête de session, pour que les propositions restent **ancrées
> dans le codebase réel** et cohérentes avec les handoffs précédents. Rédigé le 2026-07-18.

---

## 1. Ce qu'est l'application

**Contact Mailer** : gestion de contacts + envoi d'emailings + formulaires de préférences, à
destination de **petites structures** (associations, collectifs). Utilisateurs **non techniques**,
UI **en français**. Déployée en **multi-instance** (une instance = une structure, ex. « Fourmilière
Lodévois-Larzac »), chaque instance ayant sa propre config, sa DB et son image versionnée.

Fonctions principales (= menus) :
- **Contacts** : CRUD, corbeille (soft-delete), import/export (vCard, CSV), désabonnement.
- **Listes** : regroupements de contacts, push vers intégrations.
- **Mailing** : composition HTML (éditeur), aperçu, file d'envoi, historique, **demandes de
  diffusion** (reçues sur une boîte IMAP dédiée).
- **Formulaires** : formulaires de préférences publics (un contact gère ses abonnements via un
  lien personnel `/p/<token>/<uid>`).
- **Paramètres** (+ intégrations **Seafile** / **BookStack**).
- Admin : utilisateurs, apparence de la page de connexion.

## 2. Stack & contraintes techniques (IMPORTANT pour le design)

- **Backend** : Flask + Jinja2, organisé en **blueprints** (`blueprints/*.py`). Pas d'API front.
- **Front** : **pas de framework, pas de build**. Un **seul fichier** `static/style.css` (~911
  lignes) + JS inline dans les templates. **Pas de React, pas de Tailwind, pas de SASS.**
- **Éditeur mailing** : **TinyMCE 6** (via CDN). Le HTML produit doit rester **compatible email**.
- **Déploiement** : Docker, image `ghcr.io/nicolas-farrie/contact-mailer`, tags versionnés
  (`vX.Y.Z`), chaque instance épingle son tag. Version en prod actuelle : **v1.2.12**.
- **Branche de travail design** : **`design/claude-design-v2`** (forkée de `master` à jour :
  inclut tous les correctifs jusqu'à v1.2.12 + les quick wins UI). C'est la branche sur laquelle
  produire et committer les handoffs. *(L'ancienne `design/claude-design-v1` a été supprimée ;
  son contenu est dans l'historique de `master`.)*
- **Seule contrainte d'atterrissage** (n'est PAS un frein créatif) : au final, les designs seront
  ré-implémentés en **Jinja + CSS pur** (on peut **faire évoluer `style.css` et les tokens**),
  **sans framework front lourd** (pas de React/Vue/Tailwind runtime). Le niveau de modernité visé
  ci-dessous est **entièrement atteignable en CSS pur** — donc l'ambition esthétique est ouverte.
  Les prototypes `*.dc.html` sont une **référence visuelle**, pas du code à copier tel quel.

## 3. Système de design existant (tokens RÉELS — `static/style.css`)

> **Statut : point de DÉPART, pas une cible.** L'existant est volontairement basique et un peu
> vieillot. On souhaite le **faire évoluer** vers un design system moderne (tu peux proposer de
> nouveaux tokens, une nouvelle échelle typographique, un nouveau système d'espacement, etc.).
> Ce qui suit sert à (a) comprendre d'où on part, (b) garder une continuité de marque si pertinent
> (bleu primaire, vert pour les actions positives), (c) réutiliser ce qui est encore bon.

Variables `:root` :
```css
--primary: #2563eb;   --primary-dark: #1d4ed8;
--danger:  #dc2626;   --danger-dark:  #b91c1c;
--warning: #f98a38;   --warning-dark: #e07020;
--action:  #166534;   --action-dark:  #14532d;   /* vert (actions positives) */
--success: #16a34a;
--radius:  6px;
```
Classes structurantes déjà en place (à réutiliser, ne pas réinventer) :
- Layout : `.container` / `.container.container-wide` (pleine largeur), `.navbar` (+ `.nav-brand`,
  `.nav-links`, `.nav-user`, `.role-badge`, `.nav-hamburger`, `.nav-separator`).
- En-tête d'écran : `.page-header` (`h1` + `.count`).
- Boutons : `.btn` + `.btn-primary`, `.btn-secondary`, `.btn-danger`, `.btn-warning`,
  `.btn-action`, `.btn-small`, état `:disabled`.
- Conteneurs : `.form-card`, `.cards-grid` / `.card` (`.card-header` h3, `.card-description`,
  `.card-actions`).
- Alertes/flash : `.alert` + `.alert-success`, `.alert-error`, `.alert-info`.
- Palette d'appoint observée : `#dbeafe`, `#eff6ff` (bleus clairs), `#166534`/`#dcfce7` (verts),
  `#f59e0b` (ambre, pastilles « non configuré »), gris `#374151`/`#9ca3af`/`#f3f4f6`.

Layout de base (`base.html`) : `<nav class="navbar">` … puis `<main class="container {% block
container_class %}{% endblock %}">` avec `{% block content %}`. Navbar responsive (hamburger).

Écrans (templates) : `base`, `login`, `forgot_password`, `contacts`, `contact_form`, `listes`,
`liste_form`, `mailing`, `mailing_confirm`, `mailing_queue`, `mailing_history`,
`mailing_submissions`, `formulaires`, `formulaire_edit`, `formulaire_detail`,
`preferences_public`, `preferences_confirm`, `preferences_expired`, `unsubscribe`, `settings`,
`settings_layout`, `seafile`, `bookstack`, `users`, `user_form`, `profile`, `import`.

## 4. Handoffs design DÉJÀ produits (ne pas refaire)

Dans ce dossier `handoff_ClD/` :
- **`design_handoff_settings_sidebar`** — page Paramètres à 2 volets (sidebar Paramètres/Seafile/
  BookStack). Branche `design/claude-design-v1`.
- **`design_handoff_login_background`** — personnalisation de l'apparence de la page de connexion.

Format de handoff attendu (à conserver) : dossier `design_handoff_<sujet>/` avec `README.md`
(vue d'ensemble + design tokens + specs écran + **approche d'implémentation Jinja faible risque**
citant vrais templates/routes/classes), `reference_prototype/*.dc.html` (référence hi-fi), et
`proposed/` ou `code/` (Jinja/CSS/backend de référence, à adapter, pas drop-in).

## 5. État de notre travail (session debug 2026-07)

La restructuration en blueprints est faite. Une session de debug a corrigé des **bugs de fond**
(déjà livrés en v1.2.11/v1.2.12) : envoi SMTP, ids de file d'envoi, lien de formulaire cassé dans
l'email (TinyMCE relativisait les URLs). **Ces sujets sont réglés — pas du ressort du design.**

Ce qui reste et **relève de l'UI/UX** (candidats pour Claude Design) — extraits du TODO :
- **Éditeur mailing** : passer TinyMCE en **français** (langue + libellés), ajouter un bouton
  « insérer une image » ; feedback visuel du bouton d'envoi selon le résultat.
- **File d'envoi** : afficher un **état de succès explicite** (« ✓ Campagne envoyée ») ; remplacer
  le bouton dangereux « Supprimer la campagne » par un simple **« Retour »** (le delete efface
  aussi l'historique — piège).
- **Page « confirmation de l'envoi »** : le toggle « tout sélectionner » doit être **coché par
  défaut** (tous les contacts le sont déjà).
- **Formulaires** : l'écran d'édition/création est **contraint sur une demi-page** → l'étendre en
  pleine largeur (`container-wide`) ; page de confirmation « Préférences enregistrées » → ajouter
  « Revoir mes choix » / mention de réouverture via le lien.
- **Demandes de diffusion** : prévisualiser le contenu du mail depuis la liste ; **UX des pièces
  jointes** (aujourd'hui une case « Ajouter à l'envoi » décochée, trop facile à manquer) ; vue des
  demandes **archivées** (aujourd'hui invisibles).
- **Listes** : le bouton « Exporter » de chaque bloc ne doit s'afficher que pour un **admin**.
- **Paramètres** : ajouter une case « **Gestion du Bounce** » (activer/désactiver) ; câbler un
  bouton « **Envoyer un email de test** » (SMTP) ; la page pourrait être renommée « **Généraux** ».

## ⭐ Exigence d'architecture — champs « metadata-driven » (fiche contact & formulaires)

Décision prise le 2026-07-19 : la couche présentation adopte une norme où les champs sont
**pilotés par un registre de définitions**, pas codés en dur. Impact direct sur la refonte :

- La **fiche contact** et **tous les formulaires** doivent être pensés comme des **listes de champs
  pilotées par des définitions** — chaque champ a : `fieldName` (clé machine stable), `display_name`
  (libellé affiché, traduisible), `type` (text/email/number/date/select/checkbox), `group` (section),
  `ordre`, et des **hints de layout** (largeur, colonne).
- **Ne PAS maquetter les champs « en dur »** : raisonner en **groupes/sections + champs typés**, pour
  que le rendu puisse être piloté par le registre **sans figer** ni aplatir la mise en page. Le
  registre doit être assez expressif pour reproduire fidèlement la structure visuelle proposée.
- Prévoir explicitement : (a) une zone **« champs personnalisés »** (définis par l'admin) dans la
  fiche contact ; (b) un écran **admin de gestion de ces champs** dans Paramètres (CRUD des
  définitions : libellé, type, options, ordre).
- Côté stockage (transparent pour le design) : colonnes typées pour le cœur (email, nom…) + colonne
  JSON pour les champs perso. Ce qui compte pour le design : « champs = données » (groupes + types),
  pas des champs figés. Cf. [[custom-fields-design]].

Branche d'intégration : **`design/claude-design-v2`** (déjà à jour avec master). Tag stable
antérieur : `v1.3.0`. La première release de cette branche sera `v2.0.0` (refonte majeure).

## 6. Mission de la session design

**On ne cherche pas des retouches incrémentales : on veut une VISION.** Propose des **prototypes
de réorganisation de l'UI** qui repensent l'app pour un **maximum de clarté et d'utilisabilité**,
en appliquant les **canons esthétiques actuels** de ce type d'outil (apps de gestion / SaaS pour
petites structures). L'app actuelle est reconnue comme **basique et un peu vieillotte** — l'objectif
est une **montée en gamme franche**, moderne et cohérente.

Directions à explorer (non exhaustif, tu peux diverger) :
- **Design system moderne** : nouvelle échelle typographique, système d'espacement, profondeur
  (ombres douces), rayons, états (hover/focus/disabled) soignés, mode clair **et** sombre si
  pertinent, accessibilité (contrastes AA), responsive mobile-first.
- **Architecture de navigation** : repenser la structure globale (navbar actuelle vs. sidebar,
  regroupements, hiérarchie des écrans « travail quotidien » vs. « configuration »).
- **Composants récurrents** : cartes, tableaux/listes de contacts, formulaires, barres d'action,
  file d'envoi, états vides, feedback (succès/erreur/chargement), badges, toasts.
- **Parcours clés à fluidifier** : composer → confirmer → envoyer un mailing ; gérer un formulaire
  et son lien public ; traiter une demande de diffusion ; gérer contacts & listes.
- **Sécurité d'usage** : rendre les actions destructives **lisibles et non piégeuses** (cf. le
  bouton « Supprimer la campagne » qui efface l'historique) — un vrai axe de clarté.

**Périmètre : large, toute l'app** (§1 + écrans §3). Les points du TODO (§5) sont des **irritants
connus à intégrer** dans la refonte, **pas** la limite du périmètre.

**Livrables** : plusieurs **prototypes hi-fi** (`*.dc.html`) explorant des partis-pris, + pour les
directions retenues des **handoffs implémentables** (format §4) — recréables en **Jinja + CSS pur**
(tokens évolutifs), **sans framework front lourd**, pour des utilisateurs **non techniques** et
**francophones**.````
