import secrets
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.hosting.models import (
    AccessToken,
    DownloadGrant,
    Project,
    ProjectUpload,
    TransferEvent,
    VerificationRequest,
)

from .tokens import check_token_access, digest


def begin_verification(token, upload):
    upload = ProjectUpload.objects.select_related("project").get(pk=upload.pk)
    check_token_access(token, upload.project)
    if (
        upload.status != ProjectUpload.Status.READY
        or upload.project.current_upload_id != upload.pk
    ):
        raise PermissionDenied("Upload is not available.")
    code = secrets.token_urlsafe(32)
    verification = VerificationRequest.objects.create(
        token=token,
        upload=upload,
        code_hash=digest(code),
        expires_at=timezone.now() + timedelta(minutes=5),
    )
    return verification, code


@transaction.atomic
def issue_download_grant(
    token, upload, *, verification=None, risk_requires_verification=False
):
    project = Project.objects.select_for_update().get(pk=upload.project_id)
    token = AccessToken.objects.select_for_update().get(pk=token.pk)
    check_token_access(token, project)
    upload = ProjectUpload.objects.get(pk=upload.pk)
    now = timezone.now()
    if (
        project.current_upload_id != upload.pk
        or upload.status != ProjectUpload.Status.READY
    ):
        raise PermissionDenied("Upload is not available.")
    if verification is not None:
        verification = VerificationRequest.objects.select_for_update().get(
            pk=verification.pk
        )
        if (
            verification.token_id != token.pk
            or verification.upload_id != upload.pk
            or verification.status != VerificationRequest.Status.APPROVED
            or verification.verified_at is None
            or verification.expires_at <= now
            or verification.consumed_at is not None
        ):
            raise PermissionDenied("Verification is invalid, expired, or already used.")
        verification.consumed_at = now
        verification.save(update_fields=["consumed_at"])
    elif project.require_download_verification or risk_requires_verification:
        raise PermissionDenied("Download verification is required.")
    secret = secrets.token_urlsafe(32)
    grant = DownloadGrant.objects.create(
        token=token,
        upload=upload,
        verification=verification,
        secret_hash=digest(secret),
        expires_at=now + timedelta(minutes=2),
    )
    return grant, secret


@transaction.atomic
def consume_download_grant(secret, token):
    grant = (
        DownloadGrant.objects.select_related("upload")
        .filter(secret_hash=digest(secret), token_id=token.pk)
        .first()
    )
    if grant is None:
        raise PermissionDenied("Download grant is invalid.")
    project = Project.objects.select_for_update().get(pk=grant.upload.project_id)
    token = AccessToken.objects.select_for_update().get(pk=token.pk)
    check_token_access(token, project)
    upload = ProjectUpload.objects.get(pk=grant.upload_id)
    now = timezone.now()
    if (
        project.current_upload_id != upload.pk
        or upload.status != ProjectUpload.Status.READY
    ):
        raise PermissionDenied("Upload was replaced or is unavailable.")
    if project.require_download_verification and grant.verification_id is None:
        raise PermissionDenied("Download verification is required.")
    # Conditional update also prevents two consumers from redeeming one secret.
    consumed = DownloadGrant.objects.filter(
        pk=grant.pk, consumed_at__isnull=True, expires_at__gt=now
    ).update(consumed_at=now)
    if consumed != 1:
        raise PermissionDenied("Download grant expired or was already used.")
    TransferEvent.objects.create(
        user=token.user,
        project=project,
        action=TransferEvent.Action.CLONE,
        outcome=TransferEvent.Outcome.ALLOWED,
        byte_count=upload.archive_size,
    )
    return upload
