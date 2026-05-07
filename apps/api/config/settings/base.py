import os
from datetime import timedelta
from pathlib import Path

from corsheaders.defaults import default_headers
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env", encoding="utf-8-sig")


SECRET_KEY = os.getenv("SECRET_KEY", "unsafe-dev-secret-key")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "*").split(",") if host.strip()]


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "auth.apps.ApiAuthConfig",
    "audit.apps.AuditConfig",
    "tenancy",
    "branches",
    "inventory",
    "suppliers",
    "purchase_orders",
    "goods_receipts",
    "branch_transfers",
    "quick_sales",
    "reports",
    "exports.apps.ExportsConfig",
]

EXPORT_CSV_RATE_LIMIT = "20/m"
EXPORT_PDF_RATE_LIMIT = "10/m"
EXPORT_MAX_ROWS = 10000

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "tenancy.middleware.BranchContextMiddleware",
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
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


DB_SSL_REQUIRE = os.getenv("DB_SSL_REQUIRE", "false").lower() == "true"
DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
db_options = {"connect_timeout": DB_CONNECT_TIMEOUT}
if DB_SSL_REQUIRE:
    db_options["sslmode"] = "require"
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "inventory_main"),
        "USER": os.getenv("DB_USER", "inventory_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", "admin"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
        "OPTIONS": db_options,
    }
}


AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
_FRONTEND_OUT_DIR = BASE_DIR.parent / "web" / "out"
STATICFILES_DIRS = [_FRONTEND_OUT_DIR] if _FRONTEND_OUT_DIR.exists() else []

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "auth.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}


SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

AUTH_COOKIE_ACCESS = "access"
AUTH_COOKIE_REFRESH = "refresh"
AUTH_COOKIE_SECURE = not DEBUG
AUTH_COOKIE_HTTPONLY = True
AUTH_COOKIE_SAMESITE = "Lax"
AUTH_COOKIE_PATH = "/"
AUTH_COOKIE_DOMAIN = None
AUTH_COOKIE_ACCESS_MAX_AGE = 60 * 15
AUTH_COOKIE_REFRESH_MAX_AGE = 60 * 60 * 24 * 7

CSRF_COOKIE_HTTPONLY = False

# ---------------------------------------------------------------------------
# Lot / Batch + Expiry tracking feature flags
# When False, lot enforcement is skipped even if an item has is_lot_tracked=True
# ---------------------------------------------------------------------------
LOT_TRACKING_RECEIPTS_ENABLED = os.getenv("LOT_TRACKING_RECEIPTS_ENABLED", "false").lower() == "true"
LOT_TRACKING_TRANSFERS_ENABLED = os.getenv("LOT_TRACKING_TRANSFERS_ENABLED", "false").lower() == "true"
LOT_TRACKING_QUICK_SALES_ENABLED = os.getenv("LOT_TRACKING_QUICK_SALES_ENABLED", "false").lower() == "true"
LOT_TRACKING_STOCK_TAKE_ENABLED = os.getenv("LOT_TRACKING_STOCK_TAKE_ENABLED", "false").lower() == "true"
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.getenv("REDIS_URL", "redis://127.0.0.1:6379/1"),
    }
}

RATELIMIT_USE_CACHE = "default"

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

USE_EVENT_AUDIT_GOODS_RECEIPTS = os.getenv("USE_EVENT_AUDIT_GOODS_RECEIPTS", "false").lower() == "true"
USE_EVENT_AUDIT_BRANCH_TRANSFERS = os.getenv("USE_EVENT_AUDIT_BRANCH_TRANSFERS", "false").lower() == "true"
USE_EVENT_AUDIT_QUICK_SALES = os.getenv("USE_EVENT_AUDIT_QUICK_SALES", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Scan workflow feature flags — default OFF, enable per-environment
# ---------------------------------------------------------------------------
SCAN_RECEIVE_ENABLED = os.getenv("SCAN_RECEIVE_ENABLED", "false").lower() == "true"
SCAN_PICK_ENABLED = os.getenv("SCAN_PICK_ENABLED", "false").lower() == "true"
SCAN_COUNT_ENABLED = os.getenv("SCAN_COUNT_ENABLED", "false").lower() == "true"
SCAN_TRANSFER_ENABLED = os.getenv("SCAN_TRANSFER_ENABLED", "false").lower() == "true"

CORS_ALLOW_HEADERS = list(default_headers) + ["x-branch-id"]

SPECTACULAR_SETTINGS = {
    "TITLE": "Inventory API",
    "DESCRIPTION": "Multi-tenant inventory API",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

AUDIT_RETENTION_DAYS = int(os.getenv("AUDIT_RETENTION_DAYS", "180"))
