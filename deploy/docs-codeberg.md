# Publier la documentation sur Codeberg Pages

La doc (`docs/`) est un site statique MkDocs. On l'héberge sur **Codeberg Pages** (forge EU,
non-profit) : accessible **sans login**, une **source unique** pour toutes les instances, indépendante
du cycle de release de l'app.

Le **code** reste sur GitHub ; seul le **site construit** est poussé sur un dépôt Codeberg, sur une
branche `pages` que Codeberg sert automatiquement.

## Mise en place (une seule fois)

Codeberg utilise le **nouveau serveur « git-pages »** : contenu **public**, sur une branche nommée
**`pages`**, et un **webhook** qui déclenche le déploiement à chaque push. (L'ancien serveur, qui
servait sans webhook, est refusé aux comptes/orgas récents.)

1. **Compte Codeberg** : sur https://codeberg.org (gratuit).
2. **Organisation** (pour une URL propre) : créer une orga, p. ex. `contact-mailer`. Le **nom de
   l'orga = le sous-domaine** → `https://contact-mailer.codeberg.page/`.
3. **Dépôt de publication PUBLIC**, nommé **`pages`**, sous l'orga (⚠ champ *Owner* = l'orga, pas le
   compte perso). Un dépôt nommé `pages` est servi **à la racine** de l'orga (sinon `/<dépôt>/`).
4. **Clé SSH** : ajouter sa clé publique dans Codeberg (Settings → SSH / GPG Keys → onglet SSH). Sert
   au `git push`.
5. **Remote git local** :
   ```bash
   git remote add codeberg git@codeberg.org:contact-mailer/pages.git
   ```
6. **Webhook (indispensable, nouveau)** : dans le dépôt `pages` → **Settings → Webhooks → Add Webhook
   → Forgejo** :
   - **Target URL** : `https://contact-mailer.codeberg.page/`  *(le dépôt s'appelle `pages` → pas de
     `/…` à la fin ; sinon, mettre `/<dépôt>`)*
   - **Branch filter** : `pages`
   - laisser POST / `application/json` par défaut, cocher *Active*, **Add Webhook**.

   C'est ce webhook qui prévient le serveur pages à chaque push sur `pages`.

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
