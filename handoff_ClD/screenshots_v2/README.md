# Handoff : Refonte UI v2 — Contact Mailer

## Vue d'ensemble

Refonte visuelle et ergonomique complète de Contact Mailer pour des utilisateurs **non
techniques** et **francophones** de petites structures (associations, collectifs). La refonte
introduit une **architecture de navigation à sidebar gauche** (séparant « travail quotidien » et
« configuration ») et modernise tous les écrans clés autour d'un design system cohérent (fond crème
chaud, primaire indigo, vert pour les actions positives, rouge pour le destructif).

Écrans couverts par ce paquet :

1. **Contacts** (liste/tableau) — `refonte_shell_contacts.dc.html`
2. **Fiche contact** (création / modification) — `refonte_fiche_contact.dc.html`
3. **Mailing** (composer → aperçu → destinataires → envoi) — `refonte_mailing.dc.html`
4. **Formulaires** (liste, éditeur, réponses, lien, aperçu public) — `refonte_formulaires.dc.html`
5. **Demandes de diffusion** (file IMAP → mailing) — `refonte_diffusion.dc.html`
6. **Paramètres** (général, valeurs par défaut, **champs personnalisés**, intégrations) — `refonte_parametres.dc.html`
7. **Utilisateurs** (liste + saisie) — `refonte_utilisateurs.dc.html`

## À propos des fichiers de design

Les fichiers de `reference_prototype/` sont une **référence de design réalisée en HTML** — des
prototypes interactifs (`*.dc.html`) qui montrent l'apparence et le comportement voulus, **pas du
code à copier tel quel**. La tâche est de **recréer ce design dans le codebase Flask/Jinja
existant** (`nicolas-farrie/contact-mailer`, branche **`design/claude-design-v2`**) en réutilisant
ses patterns et en **faisant évoluer `static/style.css`** (tokens, échelle typo, espacements) —
**sans framework front lourd** (pas de React/Vue/Tailwind runtime). Le niveau de modernité visé est
entièrement atteignable en **CSS pur**.

Les prototypes simulent l'état via JS ; dans l'app réelle, la plomberie passe par les blueprints
Flask et les formulaires POST déjà en place.

## Fidélité

**Haute fidélité (hifi)** pour la mise en page, les couleurs, l'espacement et les états. Recréer
l'UI fidèlement, en portant les tokens ci-dessous dans `style.css`. Le contenu fonctionnel existe
déjà dans le codebase — il s'agit de le **réorganiser** dans le nouveau layout, pas de le
réinventer.

---

## ⭐ IMPORTANT — Deux changements structurants de la session (à respecter partout)

### A. Champs pilotés par le registre `fields.py` (naming des données)

La couche présentation est **metadata-driven** : les champs ne sont PAS codés en dur, ils sont
pilotés par le registre `fields.py` (déjà présent dans la branche). **Toute maquette de champ doit
être mappée sur une définition du registre.** Convention réelle :

- `key` = **fieldName** : clé machine stable (= nom de colonne, variable de fusion `{key}`, clé JSON).
- `label` = **display_name** : libellé affiché (point d'entrée i18n via `label()`).
- `type` : `text | email | tel | number | date | select | checkbox | textarea`.
- `group` : section d'affichage — `identite | contact | adresse | autres | perso`.
- `order`, `required`, `unique`, `options` (pour `select`), `help`, `width` (`full | half | third`),
  `mailing_var` (exposé comme variable de fusion `{key}` ?).

**Groupes et libellés réels** (`GROUP_LABELS`) :

| group key  | libellé affiché        |
|------------|------------------------|
| `identite` | Identité               |
| `contact`  | Coordonnées            |
| `adresse`  | Adresse                |
| `autres`   | Autres                 |
| `perso`    | Champs personnalisés   |

**Champs colonne réels** (`CONTACT_COLUMN_FIELDS`) — utiliser ces `key`/`label`/`width` exacts :

| key                  | label (affiché) | type     | group     | width | notes            |
|----------------------|-----------------|----------|-----------|-------|------------------|
| `nom`                | Nom             | text     | identite  | half  | required         |
| `prenom`             | Prénom          | text     | identite  | half  |                  |
| `genre`              | Genre           | text     | identite  | half  | ⚠ voir ci-dessous|
| `titre`              | Titre           | text     | identite  | half  |                  |
| `email`              | E-mail          | email    | contact   | half  | unique           |
| `telephone`          | Téléphone       | tel      | contact   | half  |                  |
| `organisation`       | Organisation    | text     | contact   | full  |                  |
| `adresse_rue`        | Rue             | text     | adresse   | full  |                  |
| `adresse_complement` | Complément      | text     | adresse   | full  |                  |
| `adresse_cp`         | Code postal     | text     | adresse   | third |                  |
| `adresse_ville`      | Ville           | text     | adresse   | third |                  |
| `adresse_region`     | Région          | text     | adresse   | third |                  |
| `adresse_pays`       | Pays            | text     | adresse   | half  | défaut en Paramètres |
| `source`             | Source          | text     | autres    | full  | `mailing_var=False`, lecture seule |
| `notes`              | Notes           | textarea | autres    | full  | `mailing_var=False` |

> ⚠ **Écart maquette ↔ registre à corriger côté implémentation** : la maquette Fiche contact
> affiche « Civilité » (select Madame/Monsieur/Autre) — cela correspond au champ **`genre`** du
> registre (`display_name` « Genre »). À l'implémentation, soit renommer le `display_name` de
> `genre` en « Civilité » dans le registre si c'est le libellé voulu, soit garder « Genre ». Le
> **`key` reste `genre`** dans tous les cas. Les valeurs Madame/Monsieur/Autre (et la liste des
> Titres) sont éditables via **Paramètres → Valeurs par défaut** (listes de choix Civilité/Titre).

- **Rendu par sections** : utiliser `fields_by_group()` → `{ (group_key, group_label): [FieldDef…] }`
  pour générer la fiche et les formulaires **section par section**, en respectant `width`
  (`full`/`half`/`third`) pour la disposition en colonnes.
- **Variables de fusion mailing** : `mailing_variables()` renvoie `[(key, label)…]` des champs
  `mailing_var=True`. Syntaxe éditeur : `{key}` et conditionnel `{key==valeur:si_vrai:si_faux}`
  (si_vrai/si_faux peuvent contenir des `{key}`). L'assistant variables de la maquette Mailing doit
  peupler sa liste depuis `mailing_variables()`.

### B. Champs personnalisés (`perso`) + modèle `CustomFieldDefinition`

- **Stockage** : cœur en colonnes typées (email, nom…) + **`Contact.custom_fields` (JSON)** pour
  les champs perso.
- **Définitions admin** : table **`CustomFieldDefinition`** (à créer — `fields.py` la charge déjà de
  façon tolérante via `_custom_field_defs()`, renvoie `()` tant qu'elle n'existe pas). Champs
  attendus : `key`, `display_name`, `type`, `ordre`, `options` (liste, pour `select`), `is_active`.
- **Clés réservées** : `RESERVED_KEYS` (toutes les `key` colonne + `id`, `uid`, `listes`,
  `seafile_password`, `seafile_temp_pwd`) — interdites pour un champ perso (collisions merge-vars /
  logique). La validation de création de champ doit rejeter ces clés.
- **Écran de gestion** : maquette Paramètres → onglet « Champs personnalisés » (CRUD : libellé,
  type, options, ordre par glisser/flèches, activer/désactiver). **Admin uniquement.**
- **Zone dans la fiche contact** : section « Champs personnalisés » (group `perso`), rendue comme les
  autres sections, alimentée par les définitions actives.

### C. Modalités d'accès (rôles)

Le contrôle d'accès réel se fait par décorateurs sur les blueprints (`helpers.py`) :

- **`@admin_required`** : `blueprints/users.py` (tout le CRUD utilisateurs), `blueprints/settings.py`
  (Paramètres, dont Champs personnalisés & intégrations). → Réserver ces écrans aux admins ; masquer
  leurs entrées de menu pour les non-admins.
- **`@login_required`** : `users.profile` (profil personnel).
- **Rôles** : `admin` | `user` (défaut `user`).
- **Règles UI à respecter** (déjà maquettées) :
  - Utilisateurs : on **ne peut ni désactiver ni supprimer son propre compte** (boutons désactivés,
    `user.id == current_user.id`).
  - Listes : bouton **« Exporter » réservé aux admins**.
  - Demandes de diffusion : **archiver une demande non traitée / non envoyée = admin uniquement** ;
    un `user` peut archiver un mailing déjà traité (bouton grisé sinon).

### D. Nouveau champ — Signature de modération (backend à ajouter)

- **Fiche utilisateur** : nouveau champ texte libre **optionnel** `moderation_signature` (à ajouter
  au modèle `User` + migration). Distinct du nom réel. Aide affichée : « Ce nom apparaîtra
  publiquement en bas des diffusions que vous modérez. Laissez vide pour ne pas signer. »
- **Écran d'envoi (mailing issu d'une demande de diffusion)** : case **« Signer cette diffusion »**,
  **décochée/désactivée si `current_user.moderation_signature` est vide**. Si cochée, pied de mail :
  « demande de diffusion modérée par : {moderation_signature} » (petit, en pied).

---

## Écrans (specs)

> Layout commun : **sidebar gauche fixe 236px** (`#fbfaf7`, bordure droite `#e7e5df`, sticky pleine
> hauteur) avec deux sections — **Travail** (Contacts, Listes, Mailing, Formulaires) et
> **Configuration** (Paramètres, Utilisateurs) — + bloc utilisateur en bas. **Contenu** à droite
> sur fond `#f7f6f2`, en-tête blanc `#fff` collant, cartes blanches arrondies `14px` bordées
> `#e7e5df`. Item de menu actif : texte `#33469f`, fond `#eef0fb`.

### 1. Contacts (`contacts.html`)
Tableau des contacts. Colonnes : nom/prénom (avec avatar initiales), email, **téléphone**, listes
(badges proéminents), statut (point + petit libellé, discret — pas de gros badge). Recherche,
filtres par liste, pagination. Actions par ligne (voir/modifier). Bouton « + Nouveau contact ».
Corbeille (soft-delete) accessible. Import/export (vCard, CSV) — export **admin**.

### 2. Fiche contact (`contact_form.html`)
**Page pleine** (pas modale). En-tête : avatar + nom + statut (Abonné/Désabonné) + actions
(Annuler / Enregistrer). Bandeau **désabonné → Réabonner** si applicable. Sections dans cet ordre
(rendu via `fields_by_group()`) : **Identité** (nom, prénom, genre, titre — sur une ligne),
**Coordonnées** (email, téléphone, organisation), **Listes** (cases à cocher, compteur live),
**Adresse** (rue, complément, cp/ville/région, pays), **Champs personnalisés** (`perso`), **Notes**.
Bloc **Informations système** en lecture seule : UID, source, créé/modifié par. Zone de suppression
(destructif, en bas). Respecter les `width` du registre pour les colonnes.

### 3. Mailing (`mailing.html`, `mailing_confirm.html`, `mailing_queue.html`)
Flux en 4 étapes : **Composer → Aperçu → Destinataires → Envoi**.
- **Composer** : nom du mailing éditable en en-tête ; objet ; éditeur **TinyMCE 6 en français** avec
  boutons **Insérer une image**, **Lien formulaire**, **Variable** (assistant variables piloté par
  `mailing_variables()`, avec aide au conditionnel `{key==val:vrai:faux}`) ; zone d'édition haute et
  **redimensionnable** ; **Pièces jointes** ; **Pied de mail** (désabonnement obligatoire, nom liste
  + nb inscrits, voir dans le navigateur, coordonnées) ; **Signer cette diffusion** (cf. §D) ; rail
  droit **Destinataires** (recherche + multi-listes, total dédoublonné) ; **Enregistrer le
  brouillon** avec **feedback explicite** (spinner → « ✓ Brouillon enregistré » + suite).
- **Aperçu** : navigateur de contacts (défilement des destinataires pour vérifier les variables) +
  **Envoyer un test** à sa propre adresse ; bouton **Préparer l'envoi**.
- **Destinataires** : liste **paginée**, « Tout sélectionner » **coché par défaut**, sélection
  individuelle conservée entre pages ; total « sélectionné et dédoublonné ». (Recherche
  non-destructive prévue en V2.)
- **Confirmation** : modale « Confirmer l'envoi à N contacts » (action définitive).
- **Envoi / file** : **état de succès explicite** (« ✓ Campagne envoyée ») ; **pas** de bouton
  destructif « Supprimer la campagne » (remplacé par « Retour à la file d'envoi »).

### 4. Formulaires (`formulaires.html`, `formulaire_edit.html`, `formulaire_detail.html`)
Formulaires de **préférences** publics : le contact choisit lui-même les listes/groupes qu'il
souhaite recevoir (lien personnel `/p/<token>/<uid>`).
- **Liste** : cartes (nom, statut, **date de validité**, nb réponses, actions Modifier/Réponses/Lien).
- **Éditeur** (**pleine largeur**) : message d'accueil, **date de validité** (désactive le lien
  passé cette date), **sélection des listes existantes** proposées + texte d'aide par liste,
  **consentement RGPD obligatoire** + mention légale, apparence (logo, bandeau, couleur d'accent),
  **bouton Aperçu** (page vue par le contact).
- **Réponses** : contacts ayant répondu + listes choisies ; **export CSV (admin)**.
- **Lien** : lien **nominatif, non devinable** (⚠ pas public — à transmettre par email uniquement ;
  **pas de QR code**) + activer/**archiver** (garde-fou : ne pas archiver un formulaire encore
  valide).

### 5. Demandes de diffusion (`mailing_submissions.html`)
Messages reçus sur la boîte IMAP dédiée. Encart **Fonctionnement** (texte d'origine, explicite).
Cartes : expéditeur, date, sujet, **corps tronqué à 2 lignes** avec **« Afficher le message »**
(déplie/réduit), **pièces jointes cliquables** (dev : ouvrir dans un nouvel onglet). Actions :
**Utiliser pour un mailing** (pré-remplit), **Archiver** (grisé si non-admin sur demande non
traitée, cf. §C). Ordre du sous-menu : Historique · File d'attente · Demandes de diffusion. Bouton
Actualiser. État vide + accès aux archives.

### 6. Paramètres (`settings.html` + `settings_layout.html`) — **admin**
Onglets : **Général** (nom de l'app, expéditeur : nom + adresse de réponse, apparence page de
connexion : image + assombrissement 0–70), **Valeurs par défaut** (pays par défaut avec drapeau,
indicatif tél, listes de choix **Civilité** / **Titre** éditables → alimentent `genre`/`titre`),
**Champs personnalisés** (CRUD, cf. §B), **Intégrations** (Seafile / BookStack, pastille « non
configuré »). Envisagés (TODO) : case **Gestion du Bounce**, bouton **Envoyer un email de test**
(SMTP).

### 7. Utilisateurs (`users.html`, `user_form.html`) — **admin**
Liste : avatar + nom, identifiant, rôle (badge), actif (point + libellé), actions
Modifier/Activer-Désactiver/Supprimer (désactivées sur son propre compte). Modale de saisie :
**Fiche contact liée** (select → **auto-remplit** nom/prénom/email, avec confirmation d'écrasement
si champs déjà saisis, cf. JS existant), identifiant, prénom/nom, email, **Signature de modération**
(cf. §D), rôle (Utilisateur / Administrateur), mot de passe (« laisser vide pour ne pas changer » en
édition).

---

## Design tokens (cible — à porter dans `static/style.css`)

Continuité de marque conservée (bleu primaire, vert actions) mais palette réchauffée :

```
/* Fonds */
--bg-app:        #eceae5;   /* fond général */
--bg-content:    #f7f6f2;   /* zone de contenu */
--bg-surface:    #ffffff;   /* cartes, en-têtes */
--bg-sidebar:    #fbfaf7;
--bg-muted:      #faf9f5;   /* lignes d'en-tête de tableau, zones calmes */

/* Primaire (indigo) */
--primary:       #3f56cc;
--primary-dark:  #33469f;   /* hover */
--primary-tint:  #eef0fb;   /* fond item actif / boutons secondaires */
--primary-tint2: #f5f6fd;
--primary-border:#cfd4f0;
--primary-text:  #33469f;

/* Sémantique */
--success:       #2f8a4f;  --success-text: #215e37;  --success-bg: #eaf5ee;  --success-border:#bfe0cb;
--danger:        #b23636;  --danger-bg:    #fbeeee;   --danger-border:#e0b4b4;
--warning:       #b9791a;  --warning-text: #7a5a1e;   --warning-bg: #fff3df;  --warning-border:#f0dcae;

/* Neutres (texte & bordures) */
--text:          #1c1a17;
--text-secondary:#57554e;
--text-muted:    #8a887f;
--text-faint:    #a3a196;
--border:        #e7e5df;
--border-strong: #dcdad3;
--divider:       #f0eee8;

/* Accent avatar */
--avatar-bg:     #e6e3f7;  --avatar-text: #33469f;

/* Rayons */
--radius-sm: 7px;  --radius: 9px;  --radius-lg: 14px;  --radius-pill: 99px;

/* Ombres */
--shadow-card:  0 1px 3px rgba(28,26,23,0.06);
--shadow-modal: 0 24px 60px -12px rgba(28,26,23,0.40);

/* Typo : pile système */
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
/* Échelle : h1 1.4rem/700 · h3 1rem/700 · corps 0.9–0.95rem · légende 0.8–0.82rem · label 0.82rem/600 */
```

**Focus visible** (tous les champs) : `border-color:#3f56cc; box-shadow:0 0 0 3px rgba(63,86,204,0.12)`.

## Interactions & états
- Feedback explicite sur toutes les actions asynchrones (spinner → état de succès), jamais de
  sauvegarde silencieuse (ex. brouillon).
- Actions destructives lisibles et non piégeuses (confirmations, déplacées hors du chemin principal).
- Boutons d'en-tête : `white-space:nowrap` (évite le retour à la ligne).
- Responsive : sidebar → barre horizontale / menu sur < 768px ; grilles 2–3 colonnes → 1 colonne.

## Approche d'implémentation (Jinja, faible risque)
- Réutiliser `settings_layout.html` (pattern layout + `{% block %}`) pour la sidebar de config ;
  généraliser le même principe pour la sidebar principale dans `base.html`.
- Générer fiche & formulaires depuis `fields.py` (`fields_by_group()`), pas de champs en dur.
- Créer le modèle `CustomFieldDefinition` + migration (`tools/migrate_add_custom_fields.py`) ;
  `fields.py` le consomme déjà.
- Ajouter `User.moderation_signature` + migration.
- Faire évoluer `static/style.css` avec les tokens ci-dessus (pas de framework).
- Contrôle d'accès inchangé : `@admin_required` / `@login_required` (`helpers.py`).

## Fichiers de ce paquet
- `reference_prototype/refonte_shell_contacts.dc.html` — Contacts
- `reference_prototype/refonte_fiche_contact.dc.html` — Fiche contact
- `reference_prototype/refonte_mailing.dc.html` — Mailing (4 étapes)
- `reference_prototype/refonte_formulaires.dc.html` — Formulaires
- `reference_prototype/refonte_diffusion.dc.html` — Demandes de diffusion
- `reference_prototype/refonte_parametres.dc.html` — Paramètres
- `reference_prototype/refonte_utilisateurs.dc.html` — Utilisateurs
- `reference_prototype/support.js` — runtime des prototypes (nécessaire pour les ouvrir)

Ouvrir un `.dc.html` dans un navigateur pour voir l'écran et ses interactions.

## Captures (`screenshots/`)
Captures PNG des écrans (lisibles par Claude Code) :
- `01_contacts.png` — Contacts
- `02_fiche_contact.png` — Fiche contact
- `03_mailing.png` — Mailing
- `04_formulaires.png` — Formulaires
- `05_diffusion.png` — Demandes de diffusion
- `06_parametres.png` — Paramètres ; `06b_champ_perso.png` — modale « Nouveau champ personnalisé »
- `07_utilisateurs.png` — Utilisateurs ; `07b_utilisateur_saisie.png` — modale de saisie utilisateur
