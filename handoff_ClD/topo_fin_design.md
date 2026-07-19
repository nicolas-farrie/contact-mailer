Topo à transmettre à Claude Design pour finaliser (à coller en fin de session)
==============================================================================

Trois ajouts/rappels avant de clôturer la refonte — ils ne remettent PAS en cause
le travail visuel déjà fait, ils cadrent les écrans restants :

1. FICHE CONTACT — prévoir une zone « Champs personnalisés »
   Une section (après les champs standards, avant/après les notes) destinée à
   accueillir des champs définis par l'admin : libellé + valeur, de types variés
   (texte, nombre, date, liste déroulante, case à cocher). Elle doit s'intégrer
   visuellement comme les autres groupes de champs (même style de section).

2. PARAMÈTRES — ajouter un écran « Gestion des champs personnalisés » (admin)
   Une liste des définitions de champs avec CRUD : ajouter / modifier / réordonner
   (drag ou flèches) / désactiver. Chaque définition porte : libellé affiché, type,
   options (pour les listes déroulantes), ordre. Réservé aux administrateurs.

3. RAPPEL TRANSVERSE — champs groupés, typés, à libellés explicites
   Concevoir la fiche contact ET tous les formulaires comme des champs GROUPÉS et
   TYPÉS, chaque champ = un libellé + un type + un groupe/section, avec des
   indications de largeur/disposition (pleine largeur, demi, tiers). Éviter les
   champs « en dur » implicites : l'implémentation sera pilotée par un registre de
   champs (fieldName / display_name / type / group / layout), donc le design doit
   raisonner en « champs = données », pas en champs figés. Cela n'impose aucune
   contrainte esthétique — juste une structure claire par sections.
