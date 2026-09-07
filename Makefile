IMAGE  = ghcr.io/nicolas-farrie/contact-mailer
VERSION = $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")
# Identité de la build affichée sur /a-propos (cf. Dockerfile ARG/ENV) : le commit
# exact lève l'ambiguïté d'un VERSION « -dirty », la date situe l'image dans le temps.
GIT_COMMIT = $(shell git rev-parse --short HEAD 2>/dev/null || echo "")
BUILD_DATE = $(shell date -u +%Y-%m-%dT%H:%M:%SZ)

# Écrit .version (describe + SHA de HEAD) : le conteneur n'a pas git et ne peut pas
# recalculer le tag. Le SHA sert à détecter un fichier périmé (cf. config.py).
version-file:
	@printf '%s\n%s\n' "$(VERSION)" "$(GIT_COMMIT)" > .version

# ── Dev local ────────────────────────────────────────────────────────────────
dev: version-file
	docker compose -f docker-compose.dev.yml up --build

# Comme `dev`, mais détaché (équivaut au `docker compose ... up -d` tapé à la main).
dev-up: version-file
	docker compose -f docker-compose.dev.yml up -d --build

dev-down:
	docker compose -f docker-compose.dev.yml down

# ── Build & push ─────────────────────────────────────────────────────────────
build: version-file
	docker build --build-arg APP_VERSION=$(VERSION) --build-arg GIT_COMMIT=$(GIT_COMMIT) \
		--build-arg BUILD_DATE=$(BUILD_DATE) -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .
	@echo "Image : $(IMAGE):$(VERSION)"

push: build
	docker push $(IMAGE):$(VERSION)
	docker push $(IMAGE):latest

# ── Prod locale (image registry) ─────────────────────────────────────────────
up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f

# ── Documentation (site statique MkDocs) ─────────────────────────────────────
# Dépendances isolées de l'app : pip install -r requirements-docs.txt
# Écoute sur 0.0.0.0 (accès LAN, comme docker-compose.dev) : par défaut mkdocs ne
# sert que sur 127.0.0.1, injoignable depuis une autre machine du réseau.
docs-serve:
	mkdocs serve -a 0.0.0.0:8000

docs-build:
	mkdocs build --strict

# Publie le site sur Codeberg Pages (nouveau serveur « git-pages ») : construit puis
# pousse site/ sur la branche `pages` du remote Codeberg. Prérequis (voir
# deploy/docs-codeberg.md) : un remote git `codeberg` ET un webhook Forgejo dans le
# dépôt (c'est lui qui déclenche le déploiement à chaque push sur `pages`).
CODEBERG_REMOTE ?= codeberg
CODEBERG_BRANCH ?= pages
docs-deploy: docs-build
	ghp-import --no-jekyll --push --force --remote $(CODEBERG_REMOTE) --branch $(CODEBERG_BRANCH) site

# ── Déploiement distant ───────────────────────────────────────────────────────
# Ajouter les serveurs ici : HOST=user@adresse  PATH=/chemin/sur/serveur

deploy-vps1:
	ssh user@vps1.example.com "cd /srv/docker/contact-mailer && bash deploy/update.sh"

deploy-vps2:
	ssh user@vps2.example.com "cd /srv/docker/contact-mailer && bash deploy/update.sh"

# Tout déployer d'un coup
deploy-all: deploy-vps1 deploy-vps2

.PHONY: version-file dev dev-up dev-down build push up down logs docs-serve docs-build docs-deploy deploy-vps1 deploy-vps2 deploy-all