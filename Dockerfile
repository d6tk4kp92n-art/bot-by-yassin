# Image légère pour héberger Tekkit Watch 24 h/24 (VPS, Raspberry Pi 64 bits, NAS...)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Europe/Brussels

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bot ./bot

# Utilisateur sans droits administrateur
RUN useradd --create-home --uid 1000 tekkit && mkdir -p /app/data && chown -R tekkit:tekkit /app
USER tekkit

# Base SQLite et logs : à garder dans un volume
VOLUME ["/app/data"]

CMD ["python", "-m", "bot.main"]
