FROM python:3.11-slim

ARG APP_VERSION=dev
ENV APP_VERSION=${APP_VERSION}

WORKDIR /app

# Dépendances système minimales
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Installer les dépendances Python (couche mise en cache séparément)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copier le code applicatif
COPY app.py extensions.py helpers.py models.py config.py mailer.py bookstack.py seafile.py vcard_converter.py imap_submissions.py bounce_scanner.py ./
COPY blueprints/ blueprints/
COPY tools/ tools/
COPY templates/ templates/
COPY static/ static/

# Répertoire data (sera remplacé par le volume en prod)
RUN mkdir -p data/attachments

EXPOSE 8100

CMD ["gunicorn", "--bind", "0.0.0.0:8100", "--workers", "2", "--timeout", "300", "--preload", "app:app"]