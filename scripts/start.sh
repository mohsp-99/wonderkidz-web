#!/bin/sh
# Container entrypoint: migrate, optionally seed demo content, run gunicorn.
#   PORT                 port to bind (default 8000; Render sets its own)
#   WEB_CONCURRENCY      gunicorn workers (default 3)
#   SEED_DEMO_ON_START   "true" = run seed_demo when the listings table is empty (demo hosts with ephemeral disks)
set -e
cd "$(dirname "$0")/.."

python manage.py migrate --noinput

if [ "${SEED_DEMO_ON_START:-false}" = "true" ]; then
  if python -c "import django, os, sys; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings'); django.setup(); from apps.listings.models import Listing; sys.exit(0 if Listing.objects.exists() else 1)"; then
    echo "[start] listings exist, skipping seed_demo"
  else
    echo "[start] empty database, running seed_demo"
    python manage.py seed_demo
  fi
fi

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-3}" \
  --timeout 60
