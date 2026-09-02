# L'application en 5 minutes

Ce guide donne le **modèle mental** de l'application et vous fait envoyer un premier mailing. Comptez
cinq minutes.

## Le principe en une image

L'application suit toujours le même fil : vous **rassemblez** des contacts, puis vous leur **envoyez**
un message.

```
                    ┌── Listes  (rangement figé, partagé)
   Contacts  ───────┤── Segments (recette de critères, rejouable)   ───►  Mailing
                    └── Sélection (panier de travail, éditable)
```

Vous avez **trois façons** de rassembler des destinataires (listes, segments, sélection). Elles se
complètent — inutile de toutes les maîtriser pour commencer.

## Les 5 objets, en une phrase

| Objet | En une phrase |
|---|---|
| **Contact** | Une personne : nom, e-mail (facultatif), coordonnées, champs personnalisés. |
| **Liste** | Un rangement **figé** : un contact y est, ou n'y est pas. Un contact peut être dans plusieurs listes. |
| **Segment** | Une **recette de critères** (« bounce = non ET ville = Lodève ») qui se **recalcule** à chaque usage. Il n'a pas de membres fixes. |
| **Sélection courante** | Un **panier de travail** que vous remplissez à la main, au fil de vos recherches, et que vous pouvez retoucher au contact près. |
| **Mailing** | Un e-mail personnalisé (`{prenom}`, `{nom}`…) envoyé à une liste et/ou à votre sélection. |

> **Liste vs Segment** — la distinction clé : une **liste** retient *qui* en est membre ; un
> **segment** retient *la règle*, et retrouve les contacts correspondants à chaque fois qu'on
> l'applique. Voir [Segments & Sélection](guides/segments-et-selection.md).

## Envoyer un premier mailing

**Prérequis : avoir des contacts.** Importez un fichier (Excel/CSV/vCard) ou créez une liste et
ajoutez-y des contacts. Pour un premier essai, une petite liste suffit. Ouvrez ensuite le composeur
depuis le menu latéral **Mailing → Nouveau**.

À partir de là, un mailing se déroule en **4 étapes**, rappelées par le fil affiché en haut des pages :
**Composer → Aperçu → Destinataires → Envoi**.

1. **Composer.** Vous écrivez le sujet et le message — les variables comme `{prenom}` sont remplacées
   pour chaque destinataire. Vous y choisissez aussi *à qui* envoyer : une ou plusieurs listes, et/ou
   votre sélection courante (elle apparaît en tête sous « ★ Sélection courante » si elle n'est pas
   vide).
2. **Aperçu.** Vous voyez l'email exactement tel qu'il sera reçu et faites défiler vos contacts pour
   vérifier que les variables tombent juste. Vous pouvez aussi **vous envoyer un test** sur votre
   propre adresse avant l'envoi réel.
3. **Destinataires.** Vous validez précisément qui recevra l'envoi : tout est sélectionné par défaut,
   vous pouvez décocher des contacts au cas par cas.
4. **Envoi.** L'envoi part dans une **file d'attente** avec un suivi (envoyé / en attente / erreur),
   dont vous pouvez suivre la progression.

*(Un guide Mailing détaillé viendra approfondir chacune de ces étapes — 🚧 à venir.)*

## Et ensuite ?

Dès que vous voulez cibler plus finement (« les non-répondants de tel canton », « tout le monde
sauf ceux déjà relancés »), passez au niveau 2/3 avec le guide
**[Segments & Sélection](guides/segments-et-selection.md)** — c'est le cœur de l'application.
