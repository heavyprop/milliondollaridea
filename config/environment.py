"""Small environment helpers shared by Django and development commands.

.env accepts KEY=value or quoted values, one per line. No shell expansion or
execution is performed. An existing process environment always takes precedence.
"""

import json
import os
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent


def load_environment(path=None):
    path = Path(path) if path is not None else BASE_DIR / ".env"
    if not path.exists():
        return
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, separator, value = line.partition("=")
        name, value = name.strip(), value.strip()
        if not separator or not name.isidentifier():
            raise ImproperlyConfigured(
                f"Invalid environment entry on line {line_number}."
            )
        if value.startswith('"'):
            try:
                value = json.loads(value)
            except ValueError:
                raise ImproperlyConfigured(
                    f"Invalid quoted value on line {line_number}."
                ) from None
            if not isinstance(value, str):
                raise ImproperlyConfigured(f"Expected a string on line {line_number}.")
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        os.environ.setdefault(name, value)


def required(name):
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(f"Set {name} in your environment or .env file.")
    return value


def database_config(url):
    """PostgreSQL URL for app and Go."""
    try:
        parsed = urlsplit(url)
        if (
            parsed.scheme not in {"postgres", "postgresql"}
            or not parsed.hostname
            or not parsed.path.strip("/")
        ):
            raise ValueError()
        return {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": unquote(parsed.path.lstrip("/")),
            "USER": unquote(parsed.username or ""),
            "PASSWORD": unquote(parsed.password or ""),
            "HOST": parsed.hostname,
            "PORT": parsed.port or 5432,
            "OPTIONS": dict(parse_qsl(parsed.query)),
        }
    except ValueError:
        raise ImproperlyConfigured(
            "DATABASE_URL must be a valid PostgreSQL URL."
        ) from None
