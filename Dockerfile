FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Static assets are baked into the image (served by WhiteNoise); a dummy key is enough for collectstatic.
RUN SECRET_KEY=build DEBUG=false python manage.py collectstatic --noinput

# /data is the conventional mount point for DATA_DIR (SQLite + uploads on a persistent disk). Pre-creating it
# owned by `app` makes an empty Docker named volume inherit that ownership. Group 0 + g+w keep /app and /data
# writable when the platform runs the container as an arbitrary UID (OpenShift-style, e.g. ArvanCloud).
RUN chmod +x scripts/start.sh && useradd -m app \
    && mkdir -p /data && chown -R app:0 /app /data && chmod -R g+w /app /data
USER app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD curl -fs http://localhost:8000/robots.txt || exit 1

# Migrates, optionally seeds demo data (SEED_DEMO_ON_START=true), then starts gunicorn on $PORT (default 8000).
CMD ["scripts/start.sh"]
