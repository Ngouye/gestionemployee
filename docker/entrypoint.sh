#!/bin/sh
set -e

python manage.py wait_for_db --timeout 90
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py ensure_superuser

if [ "${SEED_DEMO:-0}" = "1" ]; then
    python manage.py seed_demo --password "${DEMO_PASSWORD:-Demo2026!}"
fi

exec "$@"
