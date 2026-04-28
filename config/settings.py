from pathlib import Path
import os
from datetime import timedelta

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv
import dj_database_url

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "dev-only-insecure-secret-key-with-at-least-32-characters-12345"
)

DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() in ["true", "1"]

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS",
        "127.0.0.1,localhost,192.168.0.113"
    ).split(",")
    if host.strip()
]

if DEBUG and not ALLOWED_HOSTS:
    ALLOWED_HOSTS = ["*"]

# Respect upstream proxy headers for absolute URL generation behind Nginx.
USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://192.168.0.113:5173,https://ecomb2bapplication.onrender.com,https://sales.nxsys.in"
    ).split(",")
    if origin.strip()
]

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

# Only include Elasticsearch in production or if explicitly enabled
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

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ImproperlyConfigured("DATABASE_URL must be set for the PostgreSQL database.")

DATABASES = {
    "default": dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
        ssl_require=os.getenv("DB_SSL_REQUIRE", "True").lower() in ["true", "1"],
    )
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
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
        "anon": "1000/hour",
        "user": "5000/hour",
        "login": "20/min",
        "otp": "10/min",
        "password_reset": "10/min",
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

STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
DEFAULT_FILE_STORAGE = "cloudinary_storage.storage.MediaCloudinaryStorage"

STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")

if DEBUG and not EMAIL_HOST_USER:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
else:
    # Use Celery for async email sending in production
    EMAIL_BACKEND = os.getenv(
        "EMAIL_BACKEND",
        "djcelery_email.backends.CeleryEmailBackend" if not DEBUG else "django.core.mail.backends.smtp.EmailBackend"
    )

EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() in ["true", "1"]
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False").lower() in ["true", "1"]
EMAIL_TIMEOUT = int(os.getenv("EMAIL_TIMEOUT", "10"))
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "test@example.com")
SALES_NOTIFICATION_EMAIL = os.getenv("SALES_NOTIFICATION_EMAIL", DEFAULT_FROM_EMAIL)

# ==================== Phase 2: Email Configuration ====================
CELERY_EMAIL_TASK_CONFIG = {
    'rate_limit': '50/m',  # 50 emails per minute
}
EMAIL_RETRY_INTERVAL = int(os.getenv("EMAIL_RETRY_INTERVAL", "60"))
EMAIL_MAX_RETRIES = int(os.getenv("EMAIL_MAX_RETRIES", "3"))

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://192.168.0.113:5173")

OTP_EXPIRY_MINUTES = int(os.getenv("OTP_EXPIRY_MINUTES", "10"))
OTP_MAX_ATTEMPTS = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
OTP_RESEND_COOLDOWN_SECONDS = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))

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
        "TIMEOUT": int(os.getenv("CACHE_TIMEOUT", "3600")),  # 1 hour
    }
}

# ==================== Phase 2: Celery Configuration ====================
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = os.getenv("DJANGO_TIME_ZONE", "Asia/Kolkata")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Celery Beat Schedule for periodic tasks
CELERY_BEAT_SCHEDULE = {
    "clean-expired-otps": {
        "task": "core.tasks.clean_expired_otps",
        "schedule": 600.0,  # Every 10 minutes
    },
    "generate-analytics-snapshot": {
        "task": "core.tasks.generate_analytics_snapshot",
        "schedule": 3600.0,  # Every hour
    },
    "check-and-notify-stock-alerts": {
        "task": "core.tasks.check_stock_alerts",
        "schedule": 1800.0,  # Every 30 minutes
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ==================== Phase 2: Elasticsearch Configuration ====================
# Only configure Elasticsearch if it's enabled
if os.getenv("USE_ELASTICSEARCH", "False").lower() in ["true", "1"]:
    ELASTICSEARCH_DSL = {
        'default': {
            'hosts': os.getenv("ELASTICSEARCH_HOSTS", "http://localhost:9200").split(","),
            'timeout': 20,
            'verify_certs': os.getenv("ELASTICSEARCH_VERIFY_CERTS", "True").lower() in ["true", "1"],
            'ca_certs': os.getenv("ELASTICSEARCH_CA_CERTS", None),
            'http_auth': (
                os.getenv("ELASTICSEARCH_USERNAME", ""),
                os.getenv("ELASTICSEARCH_PASSWORD", "")
            ) if os.getenv("ELASTICSEARCH_USERNAME") else None,
        }
    }
else:
    ELASTICSEARCH_DSL = {}

# ==================== Phase 2: Analytics Configuration ====================
ANALYTICS_CACHE_TIMEOUT = int(os.getenv("ANALYTICS_CACHE_TIMEOUT", "3600"))  # 1 hour
ENABLE_ANALYTICS = os.getenv("ENABLE_ANALYTICS", "True").lower() in ["true", "1"]

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = "DENY"
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "True").lower() in ["true", "1"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
