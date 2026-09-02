IMAGE  = ghcr.io/nicolas-farrie/contact-mailer
VERSION = $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")

# ── Dev local ────────────────────────────────────────────────────────────────
dev:
	docker compose -f docker-compose.dev.yml up --build

dev-down:
	docker compose -f docker-compose.dev.yml down

# ── Build & push ─────────────────────────────────────────────────────────────
build:
	docker build --build-arg APP_VERSION=$(VERSION) -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .
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

# Publie le site sur Codeberg Pages : construit puis pousse le dossier site/ sur la
# branche `pages` du remote Codeberg. Prérequis (voir deploy/docs-codeberg.md) :
# un remote git `codeberg` pointant sur le dépôt Codeberg dédié à la doc.
CODEBERG_REMOTE ?= codeberg
docs-deploy: docs-build
	ghp-import --no-jekyll --push --force --remote $(CODEBERG_REMOTE) --branch pages site

# ── Déploiement distant ───────────────────────────────────────────────────────
# Ajouter les serveurs ici : HOST=user@adresse  PATH=/chemin/sur/serveur

deploy-vps1:
	ssh user@vps1.example.com "cd /srv/docker/contact-mailer && bash deploy/update.sh"

deploy-vps2:
	ssh user@vps2.example.com "cd /srv/docker/contact-mailer && bash deploy/update.sh"

# Tout déployer d'un coup
deploy-all: deploy-vps1 deploy-vps2

.PHONY: dev dev-down build push up down logs docs-serve docs-build docs-deploy deploy-vps1 deploy-vps2 deploy-all