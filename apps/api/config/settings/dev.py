import os

from .base import *  # noqa: F403
import sys

DEBUG = True
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", "inventory_main"),
        "USER": os.getenv("DB_USER", "inventory_user"),
        "PASSWORD": os.getenv("DB_PASSWORD", "admin"),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".localhost", "testserver", "random.host"]
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
AUTH_COOKIE_SECURE = False
_DEV_EXTRA_CORS_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DEV_CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]
_DEV_EXTRA_CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("DEV_CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
] + _DEV_EXTRA_CORS_ALLOWED_ORIGINS
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
] + _DEV_EXTRA_CSRF_TRUSTED_ORIGINS

# Local development: do not require Redis for auth rate limiting.
CACHES = {
    "default": {
        "BACKEND": (
            "django.core.cache.backends.locmem.LocMemCache"
            if "test" in sys.argv
            else "django.core.cache.backends.dummy.DummyCache"
        ),
    }
}
RATELIMIT_USE_CACHE = "default"
