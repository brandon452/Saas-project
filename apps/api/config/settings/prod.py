import config.settings.base as base_settings
from .base import *  # noqa: F403

DEBUG = False

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *base_settings.MIDDLEWARE[1:],
]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://[a-z0-9-]+\.yourapp\.com$",
]
