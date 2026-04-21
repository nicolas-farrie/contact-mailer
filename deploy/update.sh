#!/bin/bash
# Script de mise à jour côté serveur
# Lancé par : make deploy HOST=user@serveur
# Ou manuellement : bash deploy/update.sh

set -e

cd /srv/docker/contact-mailer

echo "→ Récupération du code..."
git pull

echo "→ Pull de la nouvelle image..."
docker compose pull

echo "→ Redémarrage du container..."
docker compose up -d

echo "→ Nettoyage des anciennes images..."
docker image prune -f

echo "✓ Mise à jour terminée."
docker compose ps