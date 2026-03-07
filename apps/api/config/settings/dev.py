from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", ".localhost", "*"]

CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^http://[a-z0-9-]+\.localhost:3000$",
    r"^http://localhost:3000$",
    r"^http://127\.0\.0\.1:3000$",
]
