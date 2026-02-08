#!/bin/bash
# Script d'installation Contact Mailer sur Ubuntu Server 24.04
# Usage: sudo bash install.sh

set -e

APP_DIR="/opt/contact-mailer"
REPO="https://github.com/nicolas-farrie/contact-mailer.git"

echo "=== Installation Contact Mailer ==="

# 1. Dépendances système
echo "→ Installation des paquets système..."
apt update -qq
apt install -y python3 python3-venv python3-pip git nginx

# 2. Cloner le repo
if [ -d "$APP_DIR" ]; then
    echo "→ Mise à jour du code..."
    cd "$APP_DIR" && git pull
else
    echo "→ Clonage du repo..."
    git clone "$REPO" "$APP_DIR"
fi

# 3. Environnement virtuel
echo "→ Création de l'environnement virtuel..."
cd "$APP_DIR"
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt

# 4. Fichier .env
if [ ! -f "$APP_DIR/.env" ]; then
    echo "→ Création du fichier .env..."
    cp .env.example .env
    # Générer une SECRET_KEY aléatoire
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    sed -i "s/change-me-in-production/$SECRET/" .env
    echo ""
    echo "⚠  IMPORTANT : Éditez /opt/contact-mailer/.env pour configurer :"
    echo "   - ADMIN_PASSWORD"
    echo "   - SMTP_HOST, SMTP_USER, SMTP_PASSWORD, etc."
    echo ""
fi

# 5. Créer le répertoire data et initialiser la base
mkdir -p "$APP_DIR/data"

# 6. Permissions
chown -R www-data:www-data "$APP_DIR/data"
chown www-data:www-data "$APP_DIR/.env"

# 7. Initialiser la base de données
echo "→ Initialisation de la base de données..."
cd "$APP_DIR"
source venv/bin/activate
python3 -c "from app import app, init_db; init_db()"

# 8. Service systemd
echo "→ Installation du service systemd..."
cp deploy/contact-mailer.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable contact-mailer
systemctl restart contact-mailer

# 9. Nginx
echo "→ Configuration Nginx..."
cp deploy/nginx.conf /etc/nginx/sites-available/contact-mailer
ln -sf /etc/nginx/sites-available/contact-mailer /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

echo ""
echo "=== Installation terminée ==="
echo "→ Application : http://yoursubdomain.yourdomain.ext"
echo "→ Service : systemctl status contact-mailer"
echo "→ Logs : journalctl -u contact-mailer -f"
echo ""
echo "Pour HTTPS : sudo certbot --nginx -d yourdomainname.ext"
