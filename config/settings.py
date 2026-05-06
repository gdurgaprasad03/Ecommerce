"""
Django settings for the e-commerce project.

Key changes from previous version:
1. CELERY_TASK_ALWAYS_EAGER now defaults to False (was True).
   This is the main fix that makes Celery worker actually do background work.
   To force eager mode (for tests), set env var CELERY_EAGER=True.

2. EMAIL_BACKEND logic simplified into clean if/elif/else.

3. Removed deprecated DEFAULT_FILE_STORAGE; STORAGES dict is the modern replacement.

4. ALLOWED_HOSTS in DEBUG no longer mixes "*" with specific entries.

5. CONN_HEALTH_CHECKS already correctly enabled via dj_database_url.parse().
"""
from pathlib import Path
import os
import socket
import logging.config
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import dj_database_url


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_local_ip():
    """Detect the LAN IP for cross-laptop frontend/backend testing."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


LOCAL_IP = get_local_ip()

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY")
if not SECRET_KEY or SECRET_KEY == "REPLACE_WITH_STRONG_SECRET_KEY_50_CHARS_MIN":
    if not os.getenv("DJANGO_DEBUG", "False").lower() in ["true", "1"]:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a secure random string in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(50))\""
        )
    SECRET_KEY = "dev-only-insecure-secret-key-do-not-use-in-production"

DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() in ["true", "1"]

# In DEBUG, allow LAN testing across multiple laptops. "*" alone is enough.
if DEBUG:
    ALLOWED_HOSTS = ["*"]
else:
    ALLOWED_HOSTS = [
        host.strip()
        for host in os.getenv("DJANGO_ALLOWED_HOSTS", "yourdomain.com").split(",")
        if host.strip()
    ]

if DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        "http://127.0.0.1:3000",
        "http://localhost:3000",
        f"http://{LOCAL_IP}:8000",
        f"http://{LOCAL_IP}:5173",
    ]
else:
    CSRF_TRUSTED_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "https://yourdomain.com").split(",")
        if origin.strip()
    ]

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if DEBUG:
    CORS_ALLOWED_ORIGINS = [
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://localhost:5173",
        f"http://{LOCAL_IP}:3000",
        f"http://{LOCAL_IP}:5173",
        f"http://{LOCAL_IP}:8000",
    ]
else:
    CORS_ALLOWED_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CORS_ALLOWED_ORIGINS", "https://yourdomain.com").split(",")
        if origin.strip()
    ]


# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "cloudinary_storage",
    "django.contrib.staticfiles",
    "cloudinary",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_celery_beat",
    "django_celery_results",
    "admin_interface",
    "colorfield",
]

if os.getenv("USE_ELASTICSEARCH", "False").lower() in ["true", "1"]:
    INSTALLED_APPS.append("django_elasticsearch_dsl")

INSTALLED_APPS.extend([
    "accounts",
    "products",
    "inventory",
    "orders",
    "reviews",
    "wishlist",
    "analytics",
    "search",
    "core",
])


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set for the PostgreSQL database.")

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "0")),
        conn_health_checks=os.getenv("DB_CONN_HEALTH_CHECKS", "True").lower() in ["true", "1"],
        ssl_require=os.getenv("DB_SSL_REQUIRE", "True").lower() in ["true", "1"],
    )
}


# ---------------------------------------------------------------------------
# Auth and DRF
# ---------------------------------------------------------------------------

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/min",
        "user": "1000/min",
        "login": "20/min",
        "otp": "20/min",
        "password_reset": "20/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("REFRESH_TOKEN_DAYS", "7"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ---------------------------------------------------------------------------
# Locale, static, media
# ---------------------------------------------------------------------------

LANGUAGE_CODE = "en-us"
TIME_ZONE = os.getenv("DJANGO_TIME_ZONE", "Asia/Kolkata")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": os.getenv("CLOUDINARY_CLOUD_NAME", ""),
    "API_KEY": os.getenv("CLOUDINARY_API_KEY", ""),
    "API_SECRET": os.getenv("CLOUDINARY_API_SECRET", ""),
    "SECURE": True,
}

# Modern Django storages config (Django 4.2+).
# Removed legacy DEFAULT_FILE_STORAGE — STORAGES dict is the replacement.
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

# Clean email backend resolution:
# - DEBUG without SMTP creds  -> console (prints emails to terminal)
# - DEBUG with SMTP creds      -> SMTP (or whatever EMAIL_BACKEND env says)
# - Production                 -> CeleryEmailBackend (or whatever EMAIL_BACKEND env says)
if DEBUG and not EMAIL_HOST_USER:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
elif DEBUG:
    EMAIL_BACKEND = os.getenv(
        "EMAIL_BACKEND",
        "django.core.mail.backends.smtp.EmailBackend",
    )
else:
    EMAIL_BACKEND = os.getenv(
        "EMAIL_BACKEND",
        "djcelery_email.backends.CeleryEmailBackend",
    )

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ["true", "1"]
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ["true", "1"]
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "test@example.com")
SALES_NOTIFICATION_EMAIL = os.getenv("SALES_NOTIFICATION_EMAIL", DEFAULT_FROM_EMAIL)

CELERY_EMAIL_TASK_CONFIG = {
    "rate_limit": "50/m",
}
EMAIL_RETRY_INTERVAL = int(os.getenv("EMAIL_RETRY_INTERVAL", "60"))
EMAIL_MAX_RETRIES = int(os.getenv("EMAIL_MAX_RETRIES", "3"))

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", f"http://{LOCAL_IP}:5173")


# ---------------------------------------------------------------------------
# OTP
# ---------------------------------------------------------------------------

OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": int(os.getenv("REDIS_MAX_CONNECTIONS", "50")),
                "retry_on_timeout": True,
            },
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "COMPRESSOR": "django_redis.compressors.zlib.ZlibCompressor",
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": "ecommerce",
        "TIMEOUT": int(os.getenv("CACHE_TIMEOUT", "3600")),
    }
}


# ---------------------------------------------------------------------------
# Celery
#
# CRITICAL FIX: CELERY_TASK_ALWAYS_EAGER now defaults to False.
# Previously this was hard-coded to True, which meant the running Celery
# worker never received bulk-upload tasks — they ran in the request thread,
# blocking the API response for 30+ seconds.
#
# To force eager mode (for unit tests), set the env var: CELERY_EAGER=True
# ---------------------------------------------------------------------------

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = os.getenv("DJANGO_TIME_ZONE", "Asia/Kolkata")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Eager mode is OFF by default. Set CELERY_EAGER=True in env only for tests.
CELERY_TASK_ALWAYS_EAGER = os.getenv("CELERY_EAGER", "False").lower() in ["true", "1"]
CELERY_TASK_EAGER_PROPAGATES = CELERY_TASK_ALWAYS_EAGER

CELERY_BEAT_SCHEDULE = {
    "clean-expired-otps": {
        "task": "core.tasks.clean_expired_otps",
        "schedule": 600.0,
    },
    "generate-analytics-snapshot": {
        "task": "core.tasks.generate_analytics_snapshot",
        "schedule": 3600.0,
    },
    "check-and-notify-stock-alerts": {
        "task": "core.tasks.check_stock_alerts",
        "schedule": 1800.0,
    },
}


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if os.getenv("USE_ELASTICSEARCH", "False").lower() in ["true", "1"]:
    ELASTICSEARCH_DSL = {
        "default": {
            "hosts": os.getenv("ELASTICSEARCH_HOSTS", "http://localhost:9200").split(","),
            "timeout": 20,
            "verify_certs": os.getenv("ELASTICSEARCH_VERIFY_CERTS", "True").lower() in ["true", "1"],
            "ca_certs": os.getenv("ELASTICSEARCH_CA_CERTS", None),
            "http_auth": (
                os.getenv("ELASTICSEARCH_USERNAME", ""),
                os.getenv("ELASTICSEARCH_PASSWORD", "")
            ) if os.getenv("ELASTICSEARCH_USERNAME") else None,
        }
    }
else:
    ELASTICSEARCH_DSL = {}

ANALYTICS_CACHE_TIMEOUT = int(os.getenv("ANALYTICS_CACHE_TIMEOUT", "3600"))
ENABLE_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "True").lower() in ["true", "1"]


# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
CSRF_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {asctime} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
        "file": {
            "level": "WARNING",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "django.log",
            "maxBytes": 1024 * 1024 * 10,
            "backupCount": 5,
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console", "file"] if not DEBUG else ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core.tasks": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "products.tasks": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "bulk_upload": {
            "handlers": ["console", "file"] if not DEBUG else ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

logging.config.dictConfig(LOGGING)