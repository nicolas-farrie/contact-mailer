IMAGE  = ghcr.io/nicolas-farrie/contact-mailer
VERSION = $(shell git describe --tags --always --dirty 2>/dev/null || echo "dev")

# ── Dev local ────────────────────────────────────────────────────────────────
dev:
	docker compose -f docker-compose.dev.yml up --build

dev-down:
	docker compose -f docker-compose.dev.yml down

# ── Build & push ─────────────────────────────────────────────────────────────
build:
	docker build -t $(IMAGE):$(VERSION) -t $(IMAGE):latest .
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

# ── Déploiement distant ───────────────────────────────────────────────────────
# Ajouter les serveurs ici : HOST=user@adresse  PATH=/chemin/sur/serveur

deploy-vps1:
	ssh user@vps1.example.com "cd /srv/docker/contact-mailer && bash deploy/update.sh"

deploy-vps2:
	ssh user@vps2.example.com "cd /srv/docker/contact-mailer && bash deploy/update.sh"

# Tout déployer d'un coup
deploy-all: deploy-vps1 deploy-vps2

.PHONY: dev dev-down build push up down logs deploy-vps1 deploy-vps2 deploy-all