from datetime import timedelta

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from apps.hosting.models import TransferEvent


class QuotaExceeded(Exception):
    pass


def enforce_quota(user, action, size):
    """Caller holds the user row lock, shared across their tokens/projects."""
    now = timezone.now()
    allowed = TransferEvent.objects.filter(
        user=user, outcome=TransferEvent.Outcome.ALLOWED
    )
    if action == TransferEvent.Action.PUSH:
        count = allowed.filter(
            action=action, created_at__gte=now - timedelta(hours=1)
        ).count()
        limit = getattr(settings, "HOSTING_PUBLISHES_PER_HOUR", 20)
    else:
        count = allowed.filter(
            action=action, created_at__gte=now - timedelta(days=1)
        ).count()
        limit = getattr(settings, "HOSTING_DOWNLOADS_PER_DAY", 100)
    used_bytes = (
        allowed.filter(created_at__gte=now - timedelta(days=1)).aggregate(
            total=Sum("byte_count")
        )["total"]
        or 0
    )
    if count >= limit or used_bytes + size > getattr(
        settings, "HOSTING_TRANSFER_BYTES_PER_DAY", 1024**3
    ):
        raise QuotaExceeded("Transfer limit reached. Try again later.")
