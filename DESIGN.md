# Design System — Contact Mailer

Document de référence pour Claude Design et tout travail d'évolution UI.
Généré par analyse du code existant (`static/style.css`, `templates/`).

---

## 1. Couleurs

Définies comme variables CSS dans `:root` — toujours utiliser les variables, jamais les valeurs brutes.

### Palette principale
| Variable | Valeur | Usage |
|----------|--------|-------|
| `--primary` | `#2563eb` | Boutons primaires, liens actifs, focus |
| `--primary-dark` | `#1d4ed8` | Hover bouton primaire |
| `--danger` | `#dc2626` | Suppression, erreurs |
| `--danger-dark` | `#b91c1c` | Hover danger |
| `--warning` | `#f98a38` | Modification, édition |
| `--warning-dark` | `#e07020` | Hover warning |
| `--action` | `#166534` | Actions positives (filtrer, valider) |
| `--action-dark` | `#14532d` | Hover action |
| `--success` | `#16a34a` | Messages de succès |

### Palette de gris (neutrals)
| Variable | Valeur | Usage |
|----------|--------|-------|
| `--gray-50` | `#f9fafb` | Fond hover tables, zones neutres |
| `--gray-100` | `#f3f4f6` | Fond body, bouton secondaire |
| `--gray-200` | `#e5e7eb` | Bordures, tags, séparateurs |
| `--gray-300` | `#d1d5db` | Bordures inputs, bouton default |
| `--gray-500` | `#6b7280` | Texte secondaire, hints, nav links |
| `--gray-700` | `#374151` | Labels, texte de tableau |
| `--gray-900` | `#111827` | Texte principal, navbar background |

### Couleurs fonctionnelles (alerts)
| Classe | Background | Texte | Usage |
|--------|-----------|-------|-------|
| `.alert-success` | `#dcfce7` | `#166534` | Confirmation |
| `.alert-error` | `#fee2e2` | `#991b1b` | Erreur |
| `.alert-info` | `#dbeafe` | `#1e40af` | Information neutre |
| `.tag-unsub` | `#fee2e2` | `#991b1b` | Contact désabonné |

---

## 2. Typographie

Pas de font custom — système natif uniquement (chargement immédiat, zéro dépendance réseau).

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
```

### Échelle de tailles
| Contexte | Taille | Poids |
|----------|--------|-------|
| Nav brand | `1.1rem` | `600` |
| Version tag | `0.7rem` | `normal` |
| Page title (`h1`) | `1.5rem` desktop / `1.25rem` mobile | normal |
| Body | `1rem` (base) | normal |
| Labels formulaire | `0.95rem` | `500` |
| Boutons | `0.875rem` | normal |
| Hints | `0.8rem` | normal |
| Tags / badges | `0.75rem` | normal |
| Role badge | `0.65rem` | `600` |
| Table headers | `0.85rem` | `600` |

### Couleurs de texte
- Texte principal : `var(--gray-900)`
- Texte secondaire / hints : `var(--gray-500)`
- Labels : `var(--gray-700)`
- Liens : `var(--primary)` → underline au hover

---

## 3. Espacements & Layout

- **Border radius global** : `--radius: 6px` (appliqué partout : inputs, boutons, cards, tables)
- **Line height** : `1.5`
- **Container** : `max-width: 1200px`, padding `1.5rem` (réduit à `1rem` mobile)
- **Container wide** : `max-width: none`, padding `1.5rem 2rem` (tables de données)
- **Navbar height** : `56px` (s'adapte en hauteur auto sur mobile)

---

## 4. Composants

### Navbar
```
[Contact Mailer v1.1.0]  [Contacts] [Listes] [Mailing] [Import] [Utilisateurs]  [Nom ▸admin] [Déconnexion]
```
- Fond `--gray-900`, texte blanc
- Lien actif : fond `rgba(255,255,255,0.1)`, texte blanc
- Lien normal : `--gray-300`
- `.nav-separator` : séparateur vertical `--gray-500`
- `.version-tag` : `0.7rem`, `--gray-500`, `vertical-align: middle`
- **Mobile** : hamburger `☰`, menu déroulant pleine largeur, colonne verticale

### Boutons
Tous les boutons partagent `.btn` comme base + modificateur sémantique :

| Classe | Couleur fond | Usage |
|--------|-------------|-------|
| `.btn` (default) | blanc, bordure `--gray-300` | Actions neutres, exports |
| `.btn-primary` | `--primary` | Création, action principale |
| `.btn-secondary` | `--gray-100` | Annuler, retour |
| `.btn-warning` | `--warning` | Modifier, éditer |
| `.btn-danger` | `--danger` | Supprimer |
| `.btn-action` | `--action` | Filtrer, valider (vert foncé) |
| `.btn-small` | — | Modificateur taille : `0.25rem 0.5rem`, `0.8rem` |

États : `:disabled` → `opacity: 0.4`, `pointer-events: none`

### Formulaires

**Inputs** (`input[text/email/tel/password/file]`, `textarea`, `select`) :
- Bordure `--gray-300`, radius `--radius`
- Focus : `border-color: --primary`, `box-shadow: 0 0 0 3px rgba(37,99,235,0.1)`
- Largeur 100% par défaut

**Conteneur `.form-card`** :
- Fond blanc, `padding: 1.5rem`, `border-radius: --radius`, `box-shadow: 0 1px 3px rgba(0,0,0,0.1)`
- `max-width: 600px` (pleine largeur mobile)

**Structure type** :
```html
<div class="form-group">        ← champ individuel, margin-bottom 1rem
  <label>Label *</label>
  <input ...>
  <p class="hint">Texte d'aide</p>
</div>
<div class="form-row">          ← 2 colonnes (1 col mobile)
  <div class="form-group">...</div>
  <div class="form-group">...</div>
</div>
<div class="form-actions">      ← boutons submit/cancel, flex, gap 0.5rem
  <button class="btn btn-primary">Créer</button>
  <a class="btn btn-secondary">Annuler</a>
</div>
```

**Fieldset** : `.form-fieldset` + `legend` gris `--gray-500`, pour grouper des champs liés.

### Alertes / Flash messages
```html
<div class="alert alert-success|error|info">Message</div>
```
Padding `0.75rem 1rem`, radius `--radius`, margin-bottom `1rem`. Affichées en haut du `<main>`.

### Tables de données (`.data-table`)
- Fond blanc, `border-collapse: collapse`, `box-shadow: 0 1px 3px`, overflow hidden avec radius
- Header (`th`) : fond `--gray-50`, `font-size: 0.85rem`, `color: --gray-700`
- Hover row : fond `--gray-50`
- `.col-checkbox` : `width: 40px`
- `.col-actions` : `width: 150px`
- `.actions` : `display: flex; gap: 0.25rem`
- **Tri** : clic sur `th[data-sort]` → indicateurs `▲`/`▼` en `::after`, tri alphabétique/numérique FR
- **Mobile** : `.data-table-contacts` masquée, remplacée par `.mobile-cards` (cards individuelles)

### Cards (`.card`)
- Fond blanc, radius, padding `1rem`, shadow légère
- `.card-header` : flex, space-between, h3 `1rem`
- `.card-description` : `--gray-500`, `0.875rem`
- `.card-actions` : flex, gap `0.25rem`, flex-wrap
- Grid : `.cards-grid` → `auto-fill, minmax(280px, 1fr)` (1 col mobile)

### Tags (`.tag`)
```html
<span class="tag">Nom liste</span>
```
- Fond `--gray-200`, texte `--gray-700`, radius `99px`, `0.75rem`, padding `0.125rem 0.5rem`

### Badges (`.badge`)
- Fond `--primary`, texte blanc, radius `99px`, `0.75rem`

### Info box (`.info-box`)
- Fond `--gray-50`, bordure gauche `3px solid --primary`, padding `1rem`
- Utilisée pour les blocs d'aide contextuels longs

### Page header
```html
<div class="page-header">
  <h1>Titre <span class="count">(42)</span></h1>
  <a class="btn btn-primary">+ Action</a>
</div>
```
Flex, space-between, margin-bottom `1.5rem`. `.count` en `--gray-500`, font-weight normal.

### Filters bar
```html
<div class="filters">
  <form class="filter-form">  ← flex, gap 0.5rem, flex-wrap
    <select>...</select>
    <input class="search-input">  ← min-width 200px
    <button class="btn btn-action">Filtrer</button>
    <a class="btn btn-secondary">Effacer</a>
  </form>
</div>
```
Mobile : colonne verticale, tout à 100%.

### Login
- Centré, `max-width: 360px`, margin `4rem auto`
- `.login-form` : card blanche, shadow, padding `1.5rem`
- Bouton submit pleine largeur

---

## 5. Responsive / Mobile

Breakpoint unique : `max-width: 768px`

| Élément | Desktop | Mobile |
|---------|---------|--------|
| Navbar | Horizontale, hauteur fixe 56px | Hamburger + menu vertical déroulant |
| Contacts table | `.data-table-contacts` visible | Masquée → `.mobile-cards` |
| `.form-row` | 2 colonnes | 1 colonne |
| `.cards-grid` | auto-fill minmax 280px | 1 colonne |
| `.bulk-actions` | Visible | Toggle "Actions ▾/▴" |
| Container padding | `1.5rem` | `1rem` |
| `.form-actions` | Flex horizontal | Flex vertical, boutons 100% |

---

## 6. Conventions et patterns

- **Confirmations destructives** : `onclick="return confirm('...')"` sur tous les boutons de suppression
- **État actif nav** : `class="active"` sur le lien courant via `request.endpoint`
- **Tri tables** : `data-sort` sur les `<th>` → tri client-side via `sortByTh()` dans `base.html`
- **Flash messages** : via `flask.flash(msg, 'success'|'error'|'info')`, rendu dans `base.html`
- **Hint** : `<p class="hint">` sous un champ pour aider l'utilisateur
- **Version** : `v{{ config.APP_VERSION }}` dans la nav brand via `span.version-tag`
- **Icône** : SVG natif (`contact-mailer.svg`), aussi utilisé en apple-touch-icon
- **Pas de framework CSS** : CSS vanilla uniquement, aucune dépendance externe (sauf TinyMCE via CDN dans mailing.html)
- **Pas de framework JS** : JS vanilla uniquement dans tous les templates

---

## 7. À noter pour les évolutions

- Les styles inline (`style="..."`) existent dans certains templates — à migrer vers classes CSS lors d'une refonte
- `mailing.html` est le seul template avec une dépendance CDN externe (TinyMCE)
- La couleur `--warning` (orange) est utilisée pour "Modifier" — convention à maintenir pour la cohérence
- Le vert `--action` est distinct du vert `--success` : `--action` pour les boutons d'action primaires non-destructifs, `--success` pour les états/messages
- Il n'existe pas encore de composant "modal" — les confirmations utilisent `window.confirm()` natif
