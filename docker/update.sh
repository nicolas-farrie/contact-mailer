#!/bin/bash
# deploy/update.sh — Mise à jour interactive contact-mailer
# Usage : bash deploy/update.sh
#
# Ce script :
#   1. Sauvegarde les fichiers de conf locaux (.env, docker-compose.yml, data/)
#   2. Récupère la dernière version du dépôt (git pull)
#   3. Détecte les nouvelles variables dans .env.example non présentes dans .env
#   4. Détecte les changements structurels dans docker-compose.example.yml
#   5. Pull la nouvelle image Docker
#   6. Redémarre le container
#   7. Vérifie que tout tourne
#   8. Nettoie les anciennes images
#
# Conçu pour fonctionner sur n'importe quelle instance de contact-mailer.

set -euo pipefail

# ── Couleurs ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'
CYAN='\033[0;36m'; BOLD='\033[1m'; RESET='\033[0m'

# ── Helpers ──────────────────────────────────────────────────────────────────
info()    { echo -e "${CYAN}ℹ ${RESET}$*"; }
success() { echo -e "${GREEN}✓ ${RESET}$*"; }
warn()    { echo -e "${YELLOW}⚠ ${RESET}$*"; }
error()   { echo -e "${RED}✗ ${RESET}$*" >&2; }
title()   { echo -e "\n${BOLD}══ $* ══${RESET}"; }

# Demande confirmation. Répond N par défaut si entrée vide.
confirm() {
    local msg="$1"
    echo -e -n "${YELLOW}?${RESET} ${msg} [y/N] "
    read -r answer
    [[ "$answer" =~ ^[Yy]$ ]]
}

# Demande confirmation. Répond Y par défaut si entrée vide.
confirm_yes() {
    local msg="$1"
    echo -e -n "${YELLOW}?${RESET} ${msg} [Y/n] "
    read -r answer
    [[ -z "$answer" || "$answer" =~ ^[Yy]$ ]]
}

# Pause "appuyer sur Entrée pour continuer"
pause() {
    echo -e -n "${CYAN}→ Appuyer sur Entrée pour continuer...${RESET}"
    read -r
}

# ── Répertoire de travail ────────────────────────────────────────────────────
# Fonctionne quel que soit le nom du dossier d'instance et depuis où on lance
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
INSTANCE="$(basename "$ROOT_DIR")"
cd "$ROOT_DIR"

# ── Variables de chemin ──────────────────────────────────────────────────────
ENV_FILE="$ROOT_DIR/.env"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
# Cherche dans docker/ (structure actuelle), puis deploy/ (ancienne), puis racine
if [ -f "$ROOT_DIR/docker/.env.example" ]; then
    ENV_EXAMPLE="$ROOT_DIR/docker/.env.example"
elif [ -f "$ROOT_DIR/deploy/.env.example" ]; then
    ENV_EXAMPLE="$ROOT_DIR/deploy/.env.example"
elif [ -f "$ROOT_DIR/.env.example" ]; then
    ENV_EXAMPLE="$ROOT_DIR/.env.example"
else
    ENV_EXAMPLE=""
fi
if [ -f "$ROOT_DIR/docker/docker-compose.example.yml" ]; then
    COMPOSE_EXAMPLE="$ROOT_DIR/docker/docker-compose.example.yml"
else
    COMPOSE_EXAMPLE="$ROOT_DIR/deploy/docker-compose.example.yml"
fi
DATA_DIR="$ROOT_DIR/data"
BACKUP_DIR="$ROOT_DIR/.backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$TIMESTAMP"

# ════════════════════════════════════════════════════════════════════════════
echo -e "\n${BOLD}╔══════════════════════════════════════════════════════╗"
echo -e       "║    Mise à jour contact-mailer — instance : ${INSTANCE}  "
echo -e       "╚══════════════════════════════════════════════════════╝${RESET}"
echo -e "  Dossier : $ROOT_DIR"
echo -e "  Date    : $(date '+%Y-%m-%d %H:%M:%S')\n"

# ── Pré-requis ───────────────────────────────────────────────────────────────
title "Vérification des pré-requis"

for cmd in git docker curl; do
    if command -v "$cmd" &>/dev/null; then
        success "$cmd disponible"
    else
        error "$cmd introuvable — abandon."
        exit 1
    fi
done

# Vérification accès Docker socket
if ! docker info &>/dev/null; then
    error "Accès Docker refusé (permission denied sur /var/run/docker.sock)."
    info "L'utilisateur $(whoami) n'est pas dans le groupe docker."
    info "Correction : sudo usermod -aG docker $(whoami)  puis  newgrp docker"
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    error ".env absent ($ENV_FILE) — cette instance n'est pas configurée."
    exit 1
fi
if [ ! -f "$COMPOSE_FILE" ]; then
    error "docker-compose.yml absent — abandon."
    exit 1
fi

CURRENT_IMAGE=$(grep 'image:' "$COMPOSE_FILE" | awk '{print $2}' | head -1)
info "Image actuelle dans docker-compose.yml : ${BOLD}${CURRENT_IMAGE}${RESET}"

RUNNING=$(docker compose ps --format json 2>/dev/null | python3 -c "
import sys, json
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    try:
        d=json.loads(line)
        print(d.get('State','?'), d.get('Service','?'))
    except: pass
" 2>/dev/null || echo "(impossible de lire l'état)")
info "État container actuel : $RUNNING"

# ════════════════════════════════════════════════════════════════════════════
title "Étape 1/7 — Sauvegarde des fichiers de configuration"

info "Destination : $BACKUP_PATH"
echo ""

if ! confirm_yes "Créer une sauvegarde de .env, docker-compose.yml et data/ ?"; then
    warn "Sauvegarde ignorée. Continuer sans backup est risqué."
    if ! confirm "Vraiment continuer SANS sauvegarde ?"; then
        echo "Abandon."
        exit 0
    fi
else
    mkdir -p "$BACKUP_PATH"

    # .env
    cp "$ENV_FILE" "$BACKUP_PATH/.env"
    success ".env sauvegardé"

    # docker-compose.yml
    cp "$COMPOSE_FILE" "$BACKUP_PATH/docker-compose.yml"
    success "docker-compose.yml sauvegardé"

    # data/ (copie locale légère — pour la sauvegarde distante voir backup.sh)
    if [ -d "$DATA_DIR" ]; then
        cp -r "$DATA_DIR" "$BACKUP_PATH/data"
        DATA_SIZE=$(du -sh "$BACKUP_PATH/data" | cut -f1)
        success "data/ sauvegardé ($DATA_SIZE)"
    else
        warn "Dossier data/ absent, pas de sauvegarde DB."
    fi

    success "Backup complet dans : $BACKUP_PATH"
fi

# ════════════════════════════════════════════════════════════════════════════
title "Étape 2/7 — Récupération des mises à jour (git pull)"

info "Vérification de l'état git actuel..."
if ! git fetch origin 2>/tmp/git-fetch-err; then
    if grep -q "Permission denied" /tmp/git-fetch-err; then
        warn "Erreur de droits sur .git/ (probablement des fichiers appartenant à root)."
        info "Correction : sudo chown -R $(whoami):$(whoami) $ROOT_DIR/.git"
        if confirm_yes "Lancer la correction automatiquement (sudo chown) ?"; then
            sudo chown -R "$(whoami)":"$(whoami)" "$ROOT_DIR/.git"
            git fetch origin
            success "Droits corrigés et fetch effectué."
        else
            error "Impossible de continuer sans accès à .git/ — abandon."
            exit 1
        fi
    else
        cat /tmp/git-fetch-err >&2
        error "Échec de git fetch — vérifiez la connectivité réseau et les droits."
        exit 1
    fi
fi

BEHIND=$(git rev-list HEAD..origin/$(git branch --show-current) --count 2>/dev/null || echo "?")
if [ "$BEHIND" = "0" ]; then
    info "Déjà à jour (aucun commit en retard)."
    SKIP_PULL=true
else
    info "Le dépôt est en retard de ${BOLD}${BEHIND}${RESET} commit(s)."
    echo ""
    git log HEAD..origin/$(git branch --show-current) --oneline 2>/dev/null || true
    echo ""
    SKIP_PULL=false
fi

if [ "${SKIP_PULL}" = "false" ]; then
    if ! confirm_yes "Lancer git pull ?"; then
        warn "git pull ignoré. Les fichiers .example ne seront pas mis à jour."
    else
        git pull
        success "git pull terminé."
    fi
fi

# ════════════════════════════════════════════════════════════════════════════
title "Étape 3/7 — Détection de nouvelles variables dans .env"

if [ -z "$ENV_EXAMPLE" ]; then
    warn ".env.example introuvable (ni dans deploy/ ni à la racine) — impossible de comparer."
else
    info "Référence utilisée : $ENV_EXAMPLE"
    # Extraire les clés de chaque fichier (lignes VAR= non commentées)
    keys_example=$(grep -E '^[A-Z_]+=.*' "$ENV_EXAMPLE" | cut -d= -f1 | sort)
    keys_env=$(grep -E '^[A-Z_]+=.*' "$ENV_FILE" | cut -d= -f1 | sort)

    NEW_VARS=$(comm -23 <(echo "$keys_example") <(echo "$keys_env"))

    if [ -z "$NEW_VARS" ]; then
        success "Aucune variable manquante dans .env — tout est à jour."
    else
        echo ""
        warn "Variables présentes dans .env.example mais ABSENTES de votre .env :"
        echo ""
        while IFS= read -r var; do
            # Afficher la clé + sa valeur d'exemple + commentaires qui la précèdent
            echo -e "  ${RED}+${RESET} ${BOLD}${var}${RESET}"
            grep -A1 "^${var}=" "$ENV_EXAMPLE" | head -1 | sed 's/^/      exemple: /'
        done <<< "$NEW_VARS"
        echo ""

        echo -e "Extrait de deploy/.env.example pour référence :"
        echo "────────────────────────────────────────────────"
        # Affiche les sections concernées dans .env.example
        while IFS= read -r var; do
            grep -B3 "^${var}=" "$ENV_EXAMPLE" | grep -v "^--$" || true
            grep "^${var}=" "$ENV_EXAMPLE" || true
            echo ""
        done <<< "$NEW_VARS"
        echo "────────────────────────────────────────────────"
        echo ""

        warn "Vous devez ajouter ces variables à votre .env avant de continuer."
        echo -e "  ${CYAN}nano $ENV_FILE${RESET}"
        echo ""
        pause

        # Re-vérifier après modification manuelle
        keys_env_after=$(grep -E '^[A-Z_]+=.*' "$ENV_FILE" | cut -d= -f1 | sort)
        STILL_MISSING=$(comm -23 <(echo "$keys_example") <(echo "$keys_env_after"))

        if [ -n "$STILL_MISSING" ]; then
            warn "Variables toujours manquantes : $STILL_MISSING"
            if ! confirm "Continuer quand même malgré les variables manquantes ?"; then
                echo "Abandon — complétez .env puis relancez le script."
                exit 0
            fi
        else
            success "Toutes les variables sont maintenant présentes dans .env."
        fi
    fi
fi

# ════════════════════════════════════════════════════════════════════════════
title "Étape 4/7 — Détection de changements dans docker-compose"

if [ ! -f "$COMPOSE_EXAMPLE" ]; then
    warn "deploy/docker-compose.example.yml introuvable — impossible de comparer."
else
    DIFF_COMPOSE=$(diff --unified=2 \
        <(grep -v '^#' "$COMPOSE_FILE" | sed '/^[[:space:]]*$/d') \
        <(grep -v '^#' "$COMPOSE_EXAMPLE" | sed '/^[[:space:]]*$/d') || true)

    if [ -z "$DIFF_COMPOSE" ]; then
        success "docker-compose.yml structurellement identique à l'exemple."
    else
        echo ""
        warn "Différences entre votre docker-compose.yml et l'exemple (hors commentaires) :"
        echo ""
        echo "$DIFF_COMPOSE" | sed \
            "s/^+/${GREEN}+${RESET}/; s/^-/${RED}-${RESET}/" || true
        echo ""
        info "Les lignes ${RED}-${RESET} sont dans VOTRE fichier, les ${GREEN}+${RESET} dans l'exemple."
        info "Pensez surtout à vérifier : image: (version), ports:, volumes:, command:"
        echo ""

        if confirm "Ouvrir votre docker-compose.yml dans l'éditeur pour le modifier ?"; then
            "${EDITOR:-nano}" "$COMPOSE_FILE"
        else
            warn "Vous pouvez l'éditer manuellement : nano $COMPOSE_FILE"
        fi
    fi
fi

# Afficher l'image qui sera utilisée après modifications éventuelles
NEW_IMAGE=$(grep 'image:' "$COMPOSE_FILE" | awk '{print $2}' | head -1)
info "Image qui sera utilisée : ${BOLD}${NEW_IMAGE}${RESET}"

# ════════════════════════════════════════════════════════════════════════════
title "Étape 5/7 — Pull de la nouvelle image Docker"

if ! confirm_yes "Lancer 'docker compose pull' (télécharge la nouvelle image) ?"; then
    warn "Pull ignoré. Si l'image n'a pas changé dans docker-compose.yml, aucun impact."
else
    docker compose pull
    success "Nouvelle image téléchargée."
fi

# ════════════════════════════════════════════════════════════════════════════
title "Étape 6/7 — Redémarrage du container"

echo ""
warn "Cette étape va couper brièvement le service (~2-5 secondes)."
echo ""

if ! confirm_yes "Redémarrer le container avec 'docker compose up -d' ?"; then
    warn "Redémarrage ignoré. Le container tourne encore avec l'ancienne image."
    warn "Lancez manuellement : docker compose up -d"
else
    docker compose up -d
    sleep 3
    success "Container redémarré."

    # Vérification rapide
    echo ""
    info "État après redémarrage :"
    docker compose ps

    echo ""
    info "5 dernières lignes de logs :"
    docker compose logs --tail=5 2>/dev/null || true

    # Test HTTP si BASE_URL est défini dans .env
    BASE_URL=$(grep '^BASE_URL=' "$ENV_FILE" | cut -d= -f2 | tr -d "'" | tr -d '"')
    if [ -n "$BASE_URL" ]; then
        echo ""
        info "Test HTTP : $BASE_URL"
        HTTP_CODE=$(curl -sk -o /dev/null -w '%{http_code}' "$BASE_URL" --max-time 10 || echo "ERR")
        if [[ "$HTTP_CODE" =~ ^[23] ]]; then
            success "L'application répond (HTTP $HTTP_CODE)"
        else
            warn "Réponse inattendue : HTTP $HTTP_CODE — vérifiez les logs."
        fi
    fi
fi

# ════════════════════════════════════════════════════════════════════════════
title "Étape 7/7 — Nettoyage des anciennes images"

OLD_IMAGES=$(docker images --filter "dangling=true" -q | wc -l)
if [ "$OLD_IMAGES" -eq 0 ]; then
    info "Pas d'image orpheline à supprimer."
else
    info "$OLD_IMAGES image(s) orpheline(s) détectée(s)."
    if confirm_yes "Supprimer les anciennes images inutilisées (docker image prune -f) ?"; then
        docker image prune -f
        success "Nettoyage effectué."
    fi
fi

# ════════════════════════════════════════════════════════════════════════════
echo ""
echo -e "${GREEN}${BOLD}══ Mise à jour terminée ══${RESET}"
echo ""
echo -e "  Instance : ${BOLD}${INSTANCE}${RESET}"
echo -e "  Image    : ${BOLD}${NEW_IMAGE}${RESET}"
if [ -d "$BACKUP_PATH" ]; then
    echo -e "  Backup   : ${BOLD}${BACKUP_PATH}${RESET}"
fi
echo -e "  Date     : $(date '+%Y-%m-%d %H:%M:%S')"
echo ""
info "En cas de problème, restaurez la config avec :"
echo "    cp $BACKUP_PATH/.env $ENV_FILE"
echo "    cp $BACKUP_PATH/docker-compose.yml $COMPOSE_FILE"
echo "    docker compose up -d"
echo ""
