#!/bin/bash
# Script de mise à jour d'une instance.
# À lancer DEPUIS le dossier de l'instance (ex: /srv/docker/contact-mailer-lfll) :
#     bash deploy/update.sh
# Chaque instance a son propre dossier : on opère dans le dossier courant,
# on ne code AUCUN chemin en dur (sinon on met à jour la mauvaise instance).

set -euo pipefail

# Garde-fou : on doit être dans un dossier d'instance (présence du compose).
if [ ! -f docker-compose.yml ]; then
  echo "✗ Aucun docker-compose.yml dans $(pwd)." >&2
  echo "  Lance ce script depuis le dossier de l'instance à mettre à jour." >&2
  exit 1
fi

echo "→ Instance : $(pwd)"

# 1. Sauvegarde des données AVANT toute chose (prod : contacts, file d'envoi,
#    uploads, pièces jointes). Une régression ou un pull raté reste réversible.
if [ -d data ]; then
  mkdir -p backups
  backup="backups/data-$(date +%Y%m%d-%H%M%S).tar.gz"
  echo "→ Sauvegarde des données → $backup"
  tar czf "$backup" data
  # Ne conserver que les 10 sauvegardes les plus récentes.
  ls -1t backups/data-*.tar.gz 2>/dev/null | tail -n +11 | xargs -r rm -f
else
  echo "→ (pas de dossier data/ à sauvegarder)"
fi

# 2. Code de déploiement (si l'instance est un dépôt git ; sinon on continue).
echo "→ Récupération du code de déploiement..."
git pull --ff-only 2>/dev/null || echo "  (pas un dépôt git, ou rien à tirer — on continue)"

# 3. Nouvelle image + redémarrage.
echo "→ Pull de la nouvelle image..."
docker compose pull

echo "→ Redémarrage du conteneur..."
docker compose up -d

# 4. Nettoyage.
echo "→ Nettoyage des images inutilisées..."
docker image prune -f

echo "✓ Mise à jour terminée."
docker compose ps
