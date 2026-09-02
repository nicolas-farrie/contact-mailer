# Segments & Sélection

C'est le cœur de l'application : **travailler une liste selon des critères variés, sans créer une
liste de plus à chaque fois.** Deux outils s'en chargent, complémentaires — ce guide explique lequel
sert à quoi, et comment les combiner.

## Le problème

Vous avez une grande base et vous voulez, selon les moments, « les non-répondants de Lodève », « les
élus sans e-mail », « tout le monde sauf ceux déjà relancés ». En créant une **liste** pour chacun de
ces besoins, on se retrouve vite avec trente listes à maintenir, qui se périment. Les **segments** et
la **sélection** évitent ça.

## Segment vs Sélection : la différence fondamentale

|  | **Segment** | **Sélection courante** |
|---|---|---|
| Nature | Une **recette** (des critères) | Un **ensemble figé** de contacts |
| Contenu | Pas de membres — se **recalcule** à chaque application | Les contacts que vous y avez mis |
| Édition | On ne modifie pas ses membres (il n'en a pas) : on change les critères | À la main, **au contact près** |
| Usage type | Reproductible : « les non-répondants de Lodève », toujours à jour | Ponctuel : un envoi précis, une retouche avant expédition |
| Persistance | Enregistré, réutilisable, partagé | Un panier de travail par utilisateur |

> **À retenir.** Un **segment n'a pas de membres** : il retient *la règle* et retrouve les contacts à
> chaque fois. La **sélection**, elle, retient *les contacts*. C'est pour ça qu'on retouche une
> sélection à la main, jamais un segment.

## Les segments

Un segment mémorise un jeu de **filtres avancés** sous un **nom**, pour le rejouer d'un clic.

### Créer un segment

1. Sur la page **Contacts**, dépliez **« Filtres avancés »**.
2. Ajoutez vos conditions avec **« + Ajouter une condition »** (choisissez un champ, un opérateur, une
   valeur). Les champs standards **et** personnalisés sont disponibles.
3. Choisissez comment les combiner avec **« Correspondre à : ○ toutes les conditions (ET) ○ au moins
   une (OU) »**.
4. Cliquez **« Appliquer »** pour vérifier le résultat.
5. Saisissez un nom dans **« Nom du segment… »** puis **« 💾 Enregistrer comme segment »**.

### Appliquer / supprimer

- Les segments enregistrés s'affichent sous **« Segments enregistrés : »**. **Cliquez sur son nom**
  pour l'appliquer (les contacts correspondants s'affichent, recalculés à l'instant).
- Pour en supprimer un, utilisez la croix à côté de son nom (confirmation demandée).
- **Il n'y a pas d'édition** d'un segment : pour le modifier, supprimez-le et recréez-le.

## La sélection courante

La sélection est une **liste de travail transitoire** : vous y accumulez des contacts au fil de vos
recherches, puis vous agissez dessus. **Ce n'est pas une liste** — rien n'est publié tant que vous ne
l'« enregistrez comme liste ». Son compteur est visible dans le menu latéral (**« ★ Sélection
courante »**).

### Remplir la sélection (page Contacts)

- **Contacts cochés** : cochez des lignes puis **« ★ Ajouter à la sélection »** (ou **« Retirer de la
  sélection »**).
- **Tout un résultat de filtre** : appliquez un filtre, puis **« ★ Ajouter tous ces résultats à la
  sélection »** — le serveur rejoue le filtre et ajoute **tout** le résultat, pas seulement la page
  affichée.
- **« Voir la sélection (N) »** ouvre la page de la sélection.

### Agir sur la sélection (page Sélection courante)

- **« ✉ Envoyer un mailing à cette sélection »** — ouvre le composeur avec la sélection pré-cochée.
- **« Enregistrer comme liste… »** → saisissez un « Nom de la nouvelle liste » et **« Créer la liste
  (N contact·s) »** : la sélection est figée dans une vraie liste.
- **« Ajouter à cette liste » / « Retirer de cette liste »** — applique l'appartenance à une liste
  existante pour tous les membres de la sélection.
- **« Retirer »** (sur une ligne) enlève un contact précis ; **« Vider la sélection »** la remet à
  zéro (les contacts ne sont pas supprimés).

## Recettes : combiner des critères

Le filtre avancé combine ses conditions en **ET** ou en **OU**, mais sur **un seul niveau**. Pour des
combinaisons imbriquées — typiquement `(A et B) OU (C et D)` — on assemble avec la **sélection**, par
accumulation :

**Union `(A et B) OU (C et D)` :**
1. Filtre `A et B` → **« ★ Ajouter tous ces résultats à la sélection »**.
2. Filtre `C et D` → **« ★ Ajouter tous ces résultats à la sélection »**.
3. La sélection contient l'**union** des deux groupes.

**Exclusion (retirer un groupe) :** filtrez le groupe à exclure, cochez les lignes, **« Retirer de la
sélection »**.

> 🚧 **À venir.** « Retirer *tout* le résultat d'un filtre » et « ne garder que le résultat d'un
> filtre » (intersection) en un seul bouton. Pour l'instant, le retrait passe par les cases cochées.

## Mailer un segment

Un mailing cible des **listes** et/ou la **sélection courante**. Pour envoyer à un **segment**
aujourd'hui, on passe par la sélection — deux clics :

1. **Cliquez le segment** (sous « Segments enregistrés : ») pour l'appliquer.
2. **« ★ Ajouter tous ces résultats à la sélection »**.
3. **« ✉ Envoyer un mailing à cette sélection »**.

> 🚧 **À venir.** Un bouton **✉** directement sur chaque segment, pour l'envoyer en un clic.

## Astuce : le joker dans la recherche rapide

La **barre de recherche rapide** (« Rechercher un nom ou un email… ») accepte le joker `%` de type
SQL : `uscl%bosc` trouve **usclas-du-bosc** mais **pas** *La-tour-du-bosc* (« commence par `uscl`,
finit par `bosc` »). En revanche, dans les **filtres avancés**, la valeur est prise **littéralement**
(un `%` cherche un vrai caractère `%`).
