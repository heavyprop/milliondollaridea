"""Local development: PostgreSQL and Redis, configured through .env."""

import os

from config.environment import database_config

from .base import *  # noqa: F403

DEBUG = True
SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY", "development-only-do-not-use-in-production"
)
ALLOWED_HOSTS = [
    host.strip()
    for host in os.environ.get(
        "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]"
    ).split(",")
    if host.strip()
]
DATABASES = {
    "default": database_config(
        os.environ.get(
            "DATABASE_URL",
            "postgresql://untrainable:development@127.0.0.1:5433/untrainable",
        )
    )
}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://127.0.0.1:6380/1"),
    }
}
