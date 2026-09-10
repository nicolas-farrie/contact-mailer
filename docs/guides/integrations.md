# Intégrations

Contact Mailer sait dialoguer avec d'autres outils que vous utilisez peut-être déjà : un espace de
fichiers, un wiki, un logiciel de gestion de bénévoles. Ce guide explique **ce que fait chaque
connecteur**, **comment l'activer** et **ce qu'il ne fera jamais**.

## La page Intégrations

Menu **Configuration → Intégrations** (réservé aux administrateurs). Chaque connecteur y apparaît
avec son état, qu'il soit configuré ou non :

- **Configuré** — le service auquel il est relié est indiqué, et un bouton ouvre sa page.
- **Non configuré** — la carte reste visible, en grisé, et **nomme les variables à ajouter** à votre
  fichier `.env`. Rien n'est cassé : un connecteur non configuré ne gêne personne, il attend.

> **Pourquoi les non configurés restent affichés ?** Parce que c'est par là qu'on entre pour les
> mettre en service. Les masquer supprimerait le seul chemin vers leur activation.

## Deux sens, deux usages

Le sens de circulation est indiqué sur chaque carte par une flèche, car il change tout :

|  | **Pousse vers** ↑ | **Récupère depuis** ↓ |
|---|---|---|
| Connecteurs | Seafile, BookStack | NOÉ |
| Ce qui se passe | Vos contacts deviennent des comptes sur l'autre outil | Des personnes de l'autre outil alimentent vos listes |
| Déclenchement | Vous, quand vous le décidez | Automatique, à intervalle régulier |

---

## NOÉ — bénévoles d'un événement {#noe}

[NOÉ](https://get.noe-app.io/) gère le bénévolat d'un festival : des **pôles** (accueil,
restauration, régie…), des **missions**, et des **créneaux** auxquels chaque bénévole s'inscrit
lui-même.

Le connecteur transforme **un pôle en liste de diffusion**. Vous pouvez alors écrire à « la
restauration » sans ressaisir personne, et la liste suit NOÉ toute seule.

### Configurer

Trois variables dans le fichier `.env` de l'instance, puis redémarrage :

```
NOE_URL=https://api.noe-app.io
NOE_TOKEN=
NOE_PROJECT_ID=
```

- **Le jeton** se récupère dans NOÉ : *Mon compte → Jeton d'API*. Il reste valide plus d'un an.
- **L'identifiant du projet** est celui de votre événement. Si vous ne le connaissez pas, la page
  Intégrations vous dira que la configuration est incomplète — l'équipe qui administre votre NOÉ
  saura vous le donner.

Une fois configuré, une entrée **Bénévoles NOÉ** apparaît dans le menu **Travail**, sous *Listes*.
Elle est accessible à tous les utilisateurs, pas seulement aux administrateurs : alimenter une liste
est un geste de travail, pas un réglage.

### Alimenter une liste depuis un pôle

Sur la page **Bénévoles NOÉ**, chaque pôle affiche son effectif. Le bouton *Alimenter une liste*
ouvre un écran qui, avant d'écrire quoi que ce soit, vous dit ce qui va se passer :

- combien de contacts seront **créés**, **mis à jour**, ou laissés **inchangés** ;
- quelles valeurs de NOÉ **ne seront pas appliquées** parce que le champ est déjà rempli chez vous
  (votre orthographe est conservée) ;
- quels bénévoles sont **désabonnés** — ils entreront dans la liste mais ne recevront rien ;
- quels bénévoles sont **dans la corbeille** — ils seraient recréés en double ;
- quelles adresses sont **déjà connues sous un autre nom** — deux fiches seraient créées.

Le bouton *Analyser* n'écrit rien : il montre le résultat. *Alimenter la liste* exécute.

> **À retenir.** Rien n'est jamais écrit dans NOÉ. Le connecteur est en **lecture seule** : il
> regarde, il ne modifie pas.

### Les listes alimentées sont un reflet

Une liste rattachée à un pôle porte la marque **⟳ NOÉ** et **son contenu n'est plus modifiable à la
main**. Ajouter ou retirer quelqu'un y est refusé, avec une explication.

Ce n'est pas une restriction arbitraire : le contenu vient de NOÉ, et toute modification manuelle
serait défaite à la synchronisation suivante, sans un mot. Mieux vaut refuser en expliquant que
laisser faire un geste qui sera annulé.

Vous pouvez en revanche **renommer** la liste, changer sa couleur, sa description, l'archiver ou la
supprimer — c'est son *contenu* qui est piloté, pas la liste elle-même.

### Pôles ou missions

Deux découpages du même effectif, au choix en haut de la page :

- **Pôles** — la maille habituelle : « la restauration », « l'accueil ».
- **Missions** — plus fin : « Prépa restauration », « Accueil public - Entrée ». Utile quand un pôle
  est trop large pour un message ciblé.

Seuls les groupes comptant **au moins un bénévole** sont proposés : un festival déclare ses pôles
très en amont, et lister les vides noierait ceux où il y a quelqu'un à qui écrire.

!!! warning "Attention aux doublons de réception"
    Une mission appartient à un pôle. Si vous alimentez les deux, une même personne se retrouvera
    dans deux listes. Un envoi qui vise les deux à la fois ne l'ennuiera pas — les destinataires
    sont dédoublonnés par adresse — mais **deux envois séparés lui arriveront bien deux fois**.

### La synchronisation

Les listes se mettent à jour toutes seules, à intervalle régulier. Un bénévole qui s'inscrit à un
créneau du pôle y entre ; celui qui s'en retire en sort — **mais il reste dans votre base**, avec son
historique : quitter un pôle n'est pas disparaître.

L'âge de la dernière synchronisation est affiché sur la page Bénévoles NOÉ et, surtout, **sur l'écran
d'envoi**, à côté de chaque liste concernée — en orange s'il dépasse six heures. Avant un mailing,
c'est là que ça compte.

**Ce que la synchronisation ne fait jamais :**

- elle ne **crée aucun contact** — un nouveau bénévole est signalé « en attente », à vous d'aller
  l'importer depuis la page Bénévoles NOÉ ;
- elle ne **modifie aucune fiche** : nom, adresse et téléphone vous appartiennent ;
- elle ne **réabonne personne** : un désabonnement est un droit, aucune synchronisation ne le
  révoque ;
- elle ne touche pas aux **listes archivées** — les désarchiver les remet dans le cycle.

---

## Seafile — partage de fichiers {#seafile}

[Seafile](https://www.seafile.com/) héberge vos fichiers. Le connecteur **crée les comptes** de vos
contacts et les range dans un **groupe**, pour partager un dossier avec toute une liste.

```
SEAFILE_URL=
SEAFILE_TOKEN=
```

Les contacts sont identifiés par leur **adresse e-mail**. Si le compte existe déjà, son nom est mis à
jour ; sinon il est créé avec un mot de passe temporaire, que l'application vous affiche pour que
vous le transmettiez.

---

## BookStack — documentation {#bookstack}

[BookStack](https://www.bookstackapp.com/) est un wiki. Le connecteur **crée les comptes** de vos
contacts avec un **rôle** donné, pour ouvrir l'accès à une documentation.

```
BOOKSTACK_URL=
BOOKSTACK_TOKEN_ID=
BOOKSTACK_TOKEN_SECRET=
```

Les rôles sont d'abord synchronisés depuis BookStack, puis vous choisissez celui à attribuer à une
liste de contacts.

---

## Questions fréquentes

**Faut-il configurer les connecteurs ?**
Non. Aucun n'est obligatoire. Une instance qui n'en utilise aucun fonctionne normalement, et la page
Intégrations le montrera simplement.

**Un connecteur peut-il abîmer mes données ?**
NOÉ ne peut pas : il lit, il n'écrit jamais dans le service distant, et côté Contact Mailer il ne
touche qu'à l'appartenance aux listes. Seafile et BookStack créent des comptes chez eux — ils ne
modifient pas vos contacts.

**Que se passe-t-il si le service est éteint ?**
La page du connecteur s'affiche quand même, avec la raison de l'échec. Une synchronisation qui échoue
n'interrompt pas les autres, et l'erreur est conservée pour être montrée.
