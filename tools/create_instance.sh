#!/bin/bash
# Création d'une instance Contact Mailer
# Usage : sudo bash tools/create_instance.sh --name <nom> --port <port>

set -euo pipefail

# === Paramètres ===
NAME=""
PORT=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --name) NAME="$2"; shift 2 ;;
        --port) PORT="$2"; shift 2 ;;
        *) echo "Option inconnue : $1"; exit 1 ;;
    esac
done

if [[ -z "$NAME" || -z "$PORT" ]]; then
    echo "Usage : sudo bash $0 --name <nom_instance> --port <port>"
    echo "Exemple : sudo bash $0 --name asso1 --port 5001"
    exit 1
fi

# Validation du nom (alphanumérique + tirets)
if [[ ! "$NAME" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "Erreur : le nom d'instance ne doit contenir que des lettres, chiffres, tirets et underscores."
    exit 1
fi

# Validation du port
if [[ ! "$PORT" =~ ^[0-9]+$ ]] || [[ "$PORT" -lt 1024 ]] || [[ "$PORT" -gt 65535 ]]; then
    echo "Erreur : le port doit être un nombre entre 1024 et 65535."
    exit 1
fi

SOURCE_DIR="/opt/contact-mailer"
INSTANCE_DIR="/opt/contact-mailer-instances/${NAME}"
SERVICE_NAME="contact-mailer-${NAME}"

echo "=== Création de l'instance '${NAME}' (port ${PORT}) ==="

# 1. Créer le répertoire de l'instance
if [[ -d "$INSTANCE_DIR" ]]; then
    echo "Erreur : le répertoire ${INSTANCE_DIR} existe déjà."
    exit 1
fi

mkdir -p "${INSTANCE_DIR}"
echo "  Répertoire créé : ${INSTANCE_DIR}"

# 2. Symlinks vers le code partagé
for item in app.py models.py mailer.py config.py templates static tools requirements.txt vcard_converter.py; do
    ln -s "${SOURCE_DIR}/${item}" "${INSTANCE_DIR}/${item}"
done
echo "  Symlinks créés vers le code source partagé"

# 3. Répertoire data propre + .env
mkdir -p "${INSTANCE_DIR}/data"
SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

cp "${SOURCE_DIR}/.env.example" "${INSTANCE_DIR}/.env"
# Remplacer les valeurs par défaut
sed -i "s/^SECRET_KEY=.*/SECRET_KEY=${SECRET_KEY}/" "${INSTANCE_DIR}/.env"
sed -i "s/^INSTANCE_NAME=.*/INSTANCE_NAME=${NAME}/" "${INSTANCE_DIR}/.env"
sed -i "s|^BASE_URL=.*|BASE_URL=https://listes.aubaygues.fr/${NAME}|" "${INSTANCE_DIR}/.env"

chown -R www-data:www-data "${INSTANCE_DIR}"
echo "  .env créé (SECRET_KEY auto-générée, INSTANCE_NAME=${NAME})"

# 4. Initialiser la base SQLite
cd "${INSTANCE_DIR}"
sudo -u www-data "${SOURCE_DIR}/venv/bin/python" -c "from app import db, app; app.app_context().push(); db.create_all()"
echo "  Base SQLite initialisée"

# 5. Service systemd
sed -e "s|__INSTANCE__|${NAME}|g" \
    -e "s|__PORT__|${PORT}|g" \
    -e "s|__DIR__|${INSTANCE_DIR}|g" \
    "${SOURCE_DIR}/deploy/instance.service.template" \
    > "/etc/systemd/system/${SERVICE_NAME}.service"
echo "  Service systemd créé : ${SERVICE_NAME}.service"

# 6. Bloc nginx
mkdir -p /etc/nginx/contact-mailer-instances
sed -e "s|__INSTANCE__|${NAME}|g" \
    -e "s|__PORT__|${PORT}|g" \
    "${SOURCE_DIR}/deploy/instance.nginx.template" \
    > "/etc/nginx/contact-mailer-instances/${NAME}.conf"
echo "  Config nginx créée : /etc/nginx/contact-mailer-instances/${NAME}.conf"

# 7. Instructions finales
echo ""
echo "=== Instance '${NAME}' prête ==="
echo ""
echo "Prochaines étapes :"
echo "  1. Éditer la configuration SMTP :"
echo "     sudo nano ${INSTANCE_DIR}/.env"
echo ""
echo "  2. Activer et démarrer le service :"
echo "     sudo systemctl daemon-reload"
echo "     sudo systemctl enable ${SERVICE_NAME}"
echo "     sudo systemctl start ${SERVICE_NAME}"
echo ""
echo "  3. Vérifier et recharger nginx :"
echo "     sudo nginx -t && sudo systemctl reload nginx"
echo ""
echo "  4. Accéder à l'instance :"
echo "     https://listes.aubaygues.fr/${NAME}/"
