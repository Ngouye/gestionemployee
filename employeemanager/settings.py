"""
Configuration Django d'EmployeeManager.

Toute la configuration sensible est lue depuis les variables d'environnement
(voir le fichier .env.example). Un fichier .env placé à la racine du projet est
chargé automatiquement pour le développement local.
"""
import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path):
    """Charge un fichier .env simple (CLE=valeur) sans écraser l'environnement."""
    if not path.exists():
        return
    for raw in path.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv(BASE_DIR / '.env')


def env(name, default=None):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 'yes', 'on', 'oui')


def env_list(name, default=''):
    return [item.strip() for item in os.environ.get(name, default).split(',') if item.strip()]


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Sécurité
# ---------------------------------------------------------------------------
DEBUG = env_bool('DJANGO_DEBUG', False)

SECRET_KEY = env('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if DEBUG:
        # Développement uniquement : clé éphémère (les sessions expirent à chaque redémarrage).
        SECRET_KEY = get_random_secret_key()
    else:
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY doit être défini (voir .env.example).'
        )

ALLOWED_HOSTS = env_list('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]')
CSRF_TRUSTED_ORIGINS = env_list('DJANGO_CSRF_TRUSTED_ORIGINS', '')

# Cookies sécurisés : à activer dès que l'application est servie en HTTPS.
_secure = env_bool('DJANGO_SECURE_COOKIES', False)
SESSION_COOKIE_SECURE = _secure
CSRF_COOKIE_SECURE = _secure
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = env_int('DJANGO_SESSION_AGE', 60 * 60 * 8)
SECURE_SSL_REDIRECT = env_bool('DJANGO_SSL_REDIRECT', False)
SECURE_HSTS_SECONDS = env_int('DJANGO_HSTS_SECONDS', 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = SECURE_HSTS_SECONDS > 0
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
if env_bool('DJANGO_BEHIND_PROXY', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'rest_framework',
    'rest_framework.authtoken',
    # Modules EmployeeManager
    'accounts',
    'core',
    'organization',
    'employees',
    'leaves',
    'attendance',
    'payroll',
    'expenses',
    'recruitment',
    'performance',
    'training',
    'api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.CurrentUserMiddleware',
    'accounts.middleware.ForcePasswordChangeMiddleware',
]

ROOT_URLCONF = 'employeemanager.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.app_context',
            ],
            'builtins': ['core.templatetags.core_tags'],
        },
    },
]

WSGI_APPLICATION = 'employeemanager.wsgi.application'
ASGI_APPLICATION = 'employeemanager.asgi.application'

# ---------------------------------------------------------------------------
# Base de données : DATABASE_URL (PostgreSQL) sinon SQLite local
# ---------------------------------------------------------------------------


def _database_from_url(url):
    parsed = urlparse(url)
    if parsed.scheme in ('postgres', 'postgresql', 'pgsql'):
        return {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': unquote(parsed.path.lstrip('/')),
            'USER': unquote(parsed.username or ''),
            'PASSWORD': unquote(parsed.password or ''),
            'HOST': parsed.hostname or '',
            'PORT': str(parsed.port or ''),
            'CONN_MAX_AGE': env_int('DATABASE_CONN_MAX_AGE', 60),
            'CONN_HEALTH_CHECKS': True,
        }
    if parsed.scheme == 'sqlite':
        # sqlite:///relatif.sqlite3, sqlite:////chemin/absolu.sqlite3, sqlite:///C:/chemin/windows.sqlite3
        return {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': unquote(parsed.path[1:]) or BASE_DIR / 'db.sqlite3',
        }
    raise ImproperlyConfigured(f'DATABASE_URL non supportée : {parsed.scheme}')


DATABASES = {
    'default': _database_from_url(env('DATABASE_URL'))
    if env('DATABASE_URL')
    else {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.db.DatabaseCache',
        'LOCATION': 'django_cache',
    }
}

# ---------------------------------------------------------------------------
# Authentification
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Tests : hachage rapide des mots de passe (jamais utilisé en exploitation)
if len(sys.argv) > 1 and sys.argv[1] == 'test':
    PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Verrouillage après échecs de connexion
LOGIN_MAX_ATTEMPTS = env_int('LOGIN_MAX_ATTEMPTS', 5)
LOGIN_LOCKOUT_SECONDS = env_int('LOGIN_LOCKOUT_SECONDS', 15 * 60)

# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'fr-fr'
TIME_ZONE = env('DJANGO_TIME_ZONE', 'Africa/Dakar')
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Fichiers statiques et médias
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Les médias (contrats, CV, justificatifs...) ne sont jamais servis publiquement :
# ils passent par des vues qui contrôlent les droits d'accès.
MEDIA_ROOT = Path(env('DJANGO_MEDIA_ROOT', BASE_DIR / 'media'))
MEDIA_URL = '/fichiers/'
MAX_UPLOAD_SIZE_MB = env_int('MAX_UPLOAD_SIZE_MB', 10)

STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {
        'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'
        if not DEBUG
        else 'django.contrib.staticfiles.storage.StaticFilesStorage'
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# E-mail
# ---------------------------------------------------------------------------
EMAIL_HOST = env('EMAIL_HOST', '')
if EMAIL_HOST:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_PORT = env_int('EMAIL_PORT', 587)
    EMAIL_HOST_USER = env('EMAIL_HOST_USER', '')
    EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', '')
    EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
    EMAIL_USE_SSL = env_bool('EMAIL_USE_SSL', False)
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', 'EmployeeManager <noreply@localhost>')
EMAIL_NOTIFICATIONS = env_bool('EMAIL_NOTIFICATIONS', bool(EMAIL_HOST))

# ---------------------------------------------------------------------------
# API REST
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 25,
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {'user': '1000/hour', 'anon': '30/hour'},
}

# ---------------------------------------------------------------------------
# Journalisation
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'root': {'handlers': ['console'], 'level': env('DJANGO_LOG_LEVEL', 'INFO')},
    'loggers': {
        'django.server': {'level': 'WARNING'},
    },
}

APP_NAME = 'EmployeeManager'
APP_VERSION = '2.0.0'
