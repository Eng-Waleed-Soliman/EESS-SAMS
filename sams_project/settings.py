import os
import dj_database_url
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-later")
DEBUG = os.getenv("DEBUG", "False").strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name, default=""):
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]

ALLOWED_HOSTS = _env_list(
    "ALLOWED_HOSTS",
    "127.0.0.1,localhost,app.eessports.com,eess-sams.onrender.com"
)

CSRF_TRUSTED_ORIGINS = _env_list(
    "CSRF_TRUSTED_ORIGINS",
    "https://app.eessports.com,https://eess-sams.onrender.com"
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "academies",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "academies.middleware.DatabaseRetryMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "academies.middleware.CafeteriaSpecialistAccessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "sams_project.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "academies.context_processors.app_settings",
            ]
        },
    }
]

WSGI_APPLICATION = "sams_project.wsgi.application"

DATABASE_URL = os.getenv("DATABASE_URL")

if DATABASE_URL:
    database_config = dj_database_url.config(
        default=DATABASE_URL,
        conn_max_age=60,
        conn_health_checks=True,
        disable_server_side_cursors=True,
    )
    if database_config.get("ENGINE") == "django.db.backends.postgresql":
        database_options = database_config.setdefault("OPTIONS", {})
        database_options.setdefault("sslmode", "require")
        database_options.setdefault("connect_timeout", 10)
        database_options.setdefault("keepalives", 1)
        database_options.setdefault("keepalives_idle", 30)
        database_options.setdefault("keepalives_interval", 10)
        database_options.setdefault("keepalives_count", 5)
    DATABASES = {
        "default": database_config
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "ar-eg"
TIME_ZONE = "Africa/Cairo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}
WHITENOISE_USE_FINDERS = os.getenv("WHITENOISE_USE_FINDERS", "True").strip().lower() in {"1", "true", "yes", "on"}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", str(not DEBUG)).strip().lower() in {"1", "true", "yes", "on"}
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000" if not DEBUG else "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.getenv("SECURE_HSTS_INCLUDE_SUBDOMAINS", "False").strip().lower() in {"1", "true", "yes", "on"}
SECURE_HSTS_PRELOAD = os.getenv("SECURE_HSTS_PRELOAD", "False").strip().lower() in {"1", "true", "yes", "on"}
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {"class": "logging.StreamHandler"},
    },
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "dashboard"
LOGOUT_REDIRECT_URL = "/login/"
