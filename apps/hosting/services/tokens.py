import hashlib
import secrets
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.hosting.models import AccessToken

from .access import can_access


def digest(secret):
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def issue_token(user, name, *, can_write=False, lifetime=timedelta(days=30)):
    if not user.is_active:
        raise PermissionDenied("Account is inactive.")
    if not timedelta(0) < lifetime <= timedelta(days=90):
        raise ValidationError("Token lifetime must be between zero and 90 days.")
    secret = secrets.token_urlsafe(32)
    token = AccessToken.objects.create(
        user=user,
        name=name,
        can_write=can_write,
        token_hash=digest(secret),
        expires_at=timezone.now() + lifetime,
    )
    return token, secret


def authenticate_token(secret):
    now = timezone.now()
    token = (
        AccessToken.objects.select_related("user")
        .filter(
            token_hash=digest(secret),
            revoked_at__isnull=True,
            expires_at__gt=now,
            user__is_active=True,
        )
        .first()
    )
    if token is None:
        raise PermissionDenied("Invalid or expired access token.")
    AccessToken.objects.filter(pk=token.pk).update(last_used_at=now)
    return token


def check_token_access(token, project, *, write=False):
    # Re-read persisted state so revocation is effective for existing objects.
    token = AccessToken.objects.select_related("user").get(pk=token.pk)
    if (
        token.revoked_at
        or token.expires_at <= timezone.now()
        or (write and not token.can_write)
    ):
        raise PermissionDenied("Access token cannot perform this action.")
    if not can_access(token.user, project, write=write):
        raise PermissionDenied("Project access denied.")
    return token
