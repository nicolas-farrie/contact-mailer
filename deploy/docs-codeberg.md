# Publier la documentation sur Codeberg Pages

La doc (`docs/`) est un site statique MkDocs. On l'héberge sur **Codeberg Pages** (forge EU,
non-profit) : accessible **sans login**, une **source unique** pour toutes les instances, indépendante
du cycle de release de l'app.

Le **code** reste sur GitHub ; seul le **site construit** est poussé sur un dépôt Codeberg, sur une
branche `pages` que Codeberg sert automatiquement.

## Mise en place (une seule fois)

1. **Compte Codeberg** : créer un compte sur https://codeberg.org (gratuit).
2. **Dépôt de publication** : créer un dépôt, p. ex. `contact-mailer-docs` (peut être vide).
   Codeberg Pages sert la branche `pages` de ce dépôt à l'adresse :
   `https://<utilisateur>.codeberg.page/contact-mailer-docs/`
   *(Astuce : un dépôt nommé exactement `pages` est servi à la racine
   `https://<utilisateur>.codeberg.page/` — au choix.)*
3. **Authentification** : ajouter sa **clé SSH** dans Codeberg (Settings → SSH keys), ou utiliser un
   token HTTPS. On s'en sert pour le `git push`.
4. **Remote git local** : depuis ce dépôt (contact-mailer), ajouter le remote Codeberg :
   ```bash
   git remote add codeberg git@codeberg.org:<utilisateur>/contact-mailer-docs.git
   ```

## Publier / mettre à jour

```bash
pip install -r requirements-docs.txt   # une fois (mkdocs-material + ghp-import)
make docs-serve                        # aperçu local sur http://127.0.0.1:8000
make docs-deploy                       # build + push du site sur la branche `pages` de Codeberg
```

`make docs-deploy` :
1. `mkdocs build --strict` → génère `site/` (échoue si un lien interne est cassé),
2. `ghp-import … --remote codeberg --branch pages site` → publie le contenu sur `pages`.

Codeberg Pages met le site à jour dans la minute qui suit le push.

## Notes

- **Domaine personnalisé** (optionnel) : possible via un fichier `.domains` à la racine du site — voir
  https://docs.codeberg.org/codeberg-pages/. Non requis pour démarrer.
- **Captures d'écran** : sur un site public, uniquement des captures **génériques/anonymisées** (jamais
  de vraies données contacts).
- **Automatisation CI** (plus tard) : `.github/workflows/docs.yml` valide le build à chaque PR. Un job
  de publication automatique vers Codeberg est possible en ajoutant une clé/token Codeberg dans les
  secrets GitHub — laissé manuel pour l'instant (`make docs-deploy`).
- **Rien de confidentiel** dans le site : c'est du HTML statique public, sans donnée personnelle.
