#!/usr/bin/env bash
# Lance le serveur de développement Contact Mailer.
# Usage : bash tools/devserver.sh [port]

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${1:-5000}"

cd "$PROJECT_DIR"

# Activer le virtualenv si présent
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Vérifier le .env
if [ ! -f ".env" ]; then
    echo "ATTENTION : fichier .env absent. Copier .env.example et configurer."
    echo "  cp .env.example .env"
    exit 1
fi

echo "Démarrage Contact Mailer en mode développement"
echo "  URL : http://localhost:$PORT"
echo "  Ctrl+C pour arrêter"
echo ""

exec python app.py
