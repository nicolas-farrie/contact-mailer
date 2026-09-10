FROM python:3.11-slim

# Identité de la build, injectée par le Makefile (cf. cible `build`) : version
# lisible, commit exact et date. Affichées sur /a-propos pour le débogage —
# savoir quel code tourne réellement sur une instance.
ARG APP_VERSION=dev
ARG GIT_COMMIT=
ARG BUILD_DATE=
ENV APP_VERSION=${APP_VERSION} \
    GIT_COMMIT=${GIT_COMMIT} \
    BUILD_DATE=${BUILD_DATE}

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python (couche mise en cache séparément)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code applicatif
COPY app.py extensions.py helpers.py models.py config.py mailer.py fields.py contact_set.py contact_filters.py connectors.py list_sync.py bookstack.py seafile.py noe.py vcard_converter.py imap_submissions.py bounce_scanner.py submission_notifier.py audit.py ./
COPY blueprints/ blueprints/
COPY tools/ tools/
COPY templates/ templates/
COPY static/ static/

# Répertoire data (sera remplacé par le volume en prod)
RUN mkdir -p data/attachments

EXPOSE 8100

CMD ["gunicorn", "--bind", "0.0.0.0:8100", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "--log-level", "info", "--preload", "app:app"]