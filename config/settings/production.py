"""Production requires explicit credentials, hosts, PostgreSQL, and Redis."""

from config.environment import database_config, required

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = required("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = [
    host.strip() for host in required("DJANGO_ALLOWED_HOSTS").split(",") if host.strip()
]
DATABASES = {"default": database_config(required("DATABASE_URL"))}
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": required("REDIS_URL"),
    }
}
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
