# EmployeeManager — image de production
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_MEDIA_ROOT=/app/media

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Normalise les fins de ligne du script (dépôt édité sous Windows), collecte les fichiers statiques
# et crée un utilisateur sans privilèges.
RUN sed -i 's/\r$//' docker/entrypoint.sh \
    && chmod +x docker/entrypoint.sh \
    && DJANGO_SECRET_KEY=collectstatic-only DJANGO_DEBUG=0 python manage.py collectstatic --noinput -v 0 \
    && useradd --create-home --uid 1000 app \
    && mkdir -p /app/media \
    && chown -R app:app /app/media /app/staticfiles

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/sante/', timeout=4)"

ENTRYPOINT ["/app/docker/entrypoint.sh"]
CMD ["gunicorn", "employeemanager.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "--access-logfile", "-"]
