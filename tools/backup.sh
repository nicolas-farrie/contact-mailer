#!/bin/bash
# Backup de la base de données Contact Mailer
# Usage : ./tools/backup.sh
# Crontab : 0 2 * * * /opt/contact-mailer/tools/backup.sh
#
# - Crée un dump SQLite horodaté dans data/backups/
# - Supprime les backups de plus de 30 jours
# - Compresse en gzip

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DB_PATH="$APP_DIR/data/contacts.db"
BACKUP_DIR="$APP_DIR/data/backups"
RETENTION_DAYS=30

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/contacts_${TIMESTAMP}.db"

# Vérifier que la base existe
if [ ! -f "$DB_PATH" ]; then
    echo "ERREUR : base introuvable : $DB_PATH" >&2
    exit 1
fi

# Créer le répertoire de backups
mkdir -p "$BACKUP_DIR"

# Backup via sqlite3 .backup (cohérent même si la base est utilisée)
if command -v sqlite3 &>/dev/null; then
    sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
else
    cp "$DB_PATH" "$BACKUP_FILE"
fi

# Compresser
gzip "$BACKUP_FILE"

# Supprimer les anciens backups
find "$BACKUP_DIR" -name "contacts_*.db.gz" -mtime +${RETENTION_DAYS} -delete

echo "Backup : ${BACKUP_FILE}.gz"
