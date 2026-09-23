# Intégrations

Contact Mailer sait dialoguer avec d'autres outils que vous utilisez peut-être déjà : un espace de
fichiers, un wiki, un logiciel de gestion de bénévoles. Ce guide explique **ce que fait chaque
connecteur**, **comment l'activer** et **ce qu'il ne fera jamais**.

*Guide révisé le 23/09/2026.*

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

[NOÉ](https://get.noe-app.io/) gère le bénévolat d'un festival : des **catégories** (accueil,
restauration, régie…), des **activités**, et des **créneaux** auxquels chaque bénévole s'inscrit
lui-même.

Le connecteur transforme **une catégorie en liste de diffusion**. Vous pouvez alors écrire à « la
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

### Alimenter une liste depuis une catégorie

Sur la page **Bénévoles NOÉ**, chaque catégorie affiche son effectif. Le bouton *Alimenter une liste*
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

Une liste rattachée à une catégorie porte la marque **⟳ NOÉ** et **son contenu n'est plus modifiable à la
main**. Ajouter ou retirer quelqu'un y est refusé, avec une explication.

Ce n'est pas une restriction arbitraire : le contenu vient de NOÉ, et toute modification manuelle
serait défaite à la synchronisation suivante, sans un mot. Mieux vaut refuser en expliquant que
laisser faire un geste qui sera annulé.

Vous pouvez en revanche **renommer** la liste, changer sa couleur, sa description, l'archiver ou la
supprimer — c'est son *contenu* qui est piloté, pas la liste elle-même.

### Catégories ou activités

Deux découpages du même effectif, au choix en haut de la page :

- **Catégories** — la maille habituelle : « la restauration », « l'accueil ».
- **Activités** — plus fin : « Prépa restauration », « Accueil public - Entrée ». Utile quand une catégorie
  est trop large pour un message ciblé.

Seuls les groupes comptant **au moins un bénévole** sont proposés : un festival déclare ses catégories
très en amont, et lister les vides noierait ceux où il y a quelqu'un à qui écrire.

!!! warning "Attention aux doublons de réception"
    Une activité appartient à une catégorie. Si vous alimentez les deux, une même personne se retrouvera
    dans deux listes. Un envoi qui vise les deux à la fois ne l'ennuiera pas — les destinataires
    sont dédoublonnés par adresse — mais **deux envois séparés lui arriveront bien deux fois**.

### La synchronisation

Les listes se mettent à jour toutes seules, à intervalle régulier. Un bénévole qui s'inscrit à un
créneau de la catégorie y entre ; celui qui s'en retire en sort — **mais il reste dans votre base**, avec son
historique : quitter une catégorie n'est pas disparaître.

L'âge de la dernière synchronisation est affiché sur la page Bénévoles NOÉ et, surtout, **sur l'écran
d'envoi**, à côté de chaque liste concernée — en orange s'il dépasse six heures. Avant un mailing,
c'est là que ça compte.

**Ce que la synchronisation ne fait jamais :**

- elle ne **crée aucun contact** — un nouveau bénévole est compté et signalé, à vous d'aller
  l'importer (voir ci-dessous) ;
- elle ne **modifie aucune fiche** : nom, adresse et téléphone vous appartiennent ;
- elle ne **réabonne personne** : un désabonnement est un droit, aucune synchronisation ne le
  révoque ;
- elle ne touche pas aux **listes archivées** — les désarchiver les remet dans le cycle.

### Les bénévoles qui manquent chez vous

Quelqu'un s'inscrit dans NOÉ après que vous avez alimenté la liste : il ne peut pas apparaître
tout seul dans vos contacts, puisque créer une fiche demande des décisions que vous seul pouvez
prendre — est-ce un doublon, cette personne n'était-elle pas désabonnée, faut-il la restaurer de la
corbeille ?

Alors l'application compte ces personnes et vous le dit. Sur la page **Listes**, une liste
alimentée affiche **⚠ N à examiner**. Le même signal figure sur la page Bénévoles NOÉ, sur la ligne
de la catégorie concerné.

En cliquant, vous les voyez **nommément** — prénom, nom, adresse, téléphone — avec les mêmes
avertissements que lors de la première alimentation : adresses déjà connues, contacts en corbeille,
bénévoles sans adresse email. Un bouton les crée et les ajoute à la liste.

!!! tip "Pourquoi « à examiner » et non « à importer »"
    Une personne déjà présente chez vous mais arrivée autrement qu'en venant de NOÉ apparaîtra dans
    cette liste. Elle ne sera pas dupliquée — sa fiche sera complétée — mais un coup d'œil avant
    d'importer reste utile, surtout si vous reconnaissez quelqu'un.

### Reprendre les réponses du formulaire d'inscription

NOÉ pose des questions à ses bénévoles au moment de l'inscription : compétences particulières,
formation suivie, régime alimentaire… Ces réponses peuvent descendre dans les fiches de Contact
Mailer, et servir ensuite à **constituer des groupes d'envoi** : « les bénévoles ayant une
compétence en soin », « ceux qui ont suivi la formation ».

Sur la page Bénévoles NOÉ, le bloc **Réponses du formulaire d'inscription** ouvre l'écran de
correspondance. Chaque question y est listée, et vous choisissez pour chacune :

- **ne pas la reprendre** — c'est le réglage par défaut ;
- **la reprendre dans un champ existant** de la fiche contact ;
- **créer un champ** — son nom vous est proposé, et vous pouvez l'écrire autrement. Le type suit la
  question : une liste de choix multiples reste une liste de choix multiples, avec ses options.

Le téléphone fait exception : il est **déjà repris** dans le champ prévu pour lui, et n'apparaît donc
pas dans les choix.

Les valeurs arrivent quand vous alimentez une liste ou ajoutez des nouveaux venus. Pour les
rafraîchir sans rien ajouter d'autre, le bouton **⟳ Actualiser les réponses depuis NOÉ** reprend les
réponses de tout le groupe.

### Un champ alimenté par NOÉ est un reflet

Comme une liste alimentée, un champ repris de NOÉ porte la marque **⟳** et **n'est pas modifiable
dans la fiche** : il se corrige dans NOÉ. Ce que NOÉ dit remplace ce qui est ici — **y compris quand
la réponse disparaît**. Un bénévole qui retire une compétence la voit disparaître chez vous aussi,
faute de quoi un groupe « les soignants » garderait quelqu'un qui s'est retiré.

Vos données d'identité, elles, restent les vôtres : nom, prénom, adresse et téléphone se modifient
normalement, et **une réponse vide dans NOÉ n'efface jamais** ce que vous avez saisi.

!!! warning "La qualité des réponses se joue dans NOÉ"
    Si la question laisse écrire librement, « médecin », « Médecin » et « toubib » seront trois
    réponses différentes, et un groupe en oubliera. Quand la donnée sert à cibler, mieux vaut une
    question à choix — et les corrections se font dans NOÉ, puisque c'est lui qui fait foi.

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

**Pourquoi ne puis-je pas corriger un champ venu de NOÉ ?**
Parce que la correction serait défaite à la prochaine reprise des réponses, sans un mot. Le champ
porte la marque ⟳ : il se corrige dans NOÉ, qui fait foi pour ces informations-là. Vos données
d'identité, elles, restent modifiables normalement.

**Un bénévole a retiré une compétence dans NOÉ : que devient-elle chez moi ?**
Elle disparaît à la prochaine reprise des réponses. C'est voulu : sans cela, un groupe constitué sur
cette compétence garderait quelqu'un qui s'en est retiré.

**Que se passe-t-il si le service est éteint ?**
La page du connecteur s'affiche quand même, avec la raison de l'échec. Une synchronisation qui échoue
n'interrompt pas les autres, et l'erreur est conservée pour être montrée.
