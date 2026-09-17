"""Shared application configuration. Choose development or production."""

import os

from config.environment import BASE_DIR, load_environment

load_environment(os.environ.get("DJANGO_ENV_FILE"))

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.accounts.apps.AccountsConfig",
    "apps.notifcation.apps.NotifcationConfig",
    "apps.discussions.apps.DiscussionsConfig",
    "apps.feed.apps.FeedConfig",
    "apps.search.apps.SearchConfig",
    "apps.recommendations.apps.RecommendationsConfig",
    "apps.hosting.apps.HostingConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/accounts/"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
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
STATICFILES_DIRS = [BASE_DIR / "static"]

# Private archives must never be exposed through static/media hosting.
HOSTING_STORAGE_ROOT = BASE_DIR / os.environ.get(
    "HOSTING_STORAGE_ROOT", "private_hosting"
)
HOSTING_MAX_ARCHIVE_BYTES = 25 * 1024 * 1024
HOSTING_MAX_UNPACKED_BYTES = 100 * 1024 * 1024
HOSTING_MAX_FILES = 2000
HOSTING_PUBLISHES_PER_HOUR = 20
HOSTING_DOWNLOADS_PER_DAY = 100
HOSTING_TRANSFER_BYTES_PER_DAY = 1024**3

GO_SEARCH_URL = os.environ.get("GO_SEARCH_URL", "http://127.0.0.1:8080/search")
MAILERS = {"default": {"BACKEND": "django.core.mail.backends.console.EmailBackend"}}
