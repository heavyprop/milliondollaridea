"""Shared access rules for transfers. API views enforce account quotas.

These helpers do not validate CAPTCHA responses or enforce network rate limits.
"""

import hashlib
import secrets
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import AccessToken, DownloadGrant, Project, ProjectMembership, ProjectUpload, TransferEvent, VerificationRequest


def digest(secret):
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def can_access(user, project, *, write=False):
    if not user.is_authenticated or not user.is_active:
        return False
    if write and project.is_archived:
        return False
    if project.owner_id == user.pk:
        return True
    if not write and project.visibility == Project.Visibility.MEMBERS:
        return True
    memberships = ProjectMembership.objects.filter(project=project, user=user)
    if write:
        memberships = memberships.filter(role=ProjectMembership.Role.WRITER)
    return memberships.exists()


def issue_token(user, name, *, can_write=False, lifetime=timedelta(days=30)):
    if not user.is_active:
        raise PermissionDenied("Account is inactive.")
    if not timedelta(0) < lifetime <= timedelta(days=90):
        raise ValidationError("Token lifetime must be between zero and 90 days.")
    secret = secrets.token_urlsafe(32)
    token = AccessToken.objects.create(user=user, name=name, can_write=can_write, token_hash=digest(secret), expires_at=timezone.now() + lifetime)
    return token, secret


def authenticate_token(secret):
    now = timezone.now()
    token = AccessToken.objects.select_related("user").filter(token_hash=digest(secret), revoked_at__isnull=True, expires_at__gt=now, user__is_active=True).first()
    if token is None:
        raise PermissionDenied("Invalid or expired access token.")
    AccessToken.objects.filter(pk=token.pk).update(last_used_at=now)
    return token


def check_token_access(token, project, *, write=False):
    # Re-read persisted state so revocation is effective for existing objects.
    token = AccessToken.objects.select_related("user").get(pk=token.pk)
    if token.revoked_at or token.expires_at <= timezone.now() or (write and not token.can_write):
        raise PermissionDenied("Access token cannot perform this action.")
    if not can_access(token.user, project, write=write):
        raise PermissionDenied("Project access denied.")
    return token


def begin_verification(token, upload):
    upload = ProjectUpload.objects.select_related("project").get(pk=upload.pk)
    check_token_access(token, upload.project)
    if upload.status != ProjectUpload.Status.READY or upload.project.current_upload_id != upload.pk:
        raise PermissionDenied("Upload is not available.")
    code = secrets.token_urlsafe(32)
    verification = VerificationRequest.objects.create(token=token, upload=upload, code_hash=digest(code), expires_at=timezone.now() + timedelta(minutes=5))
    return verification, code


@transaction.atomic
def publish_validated_upload(upload, token):
    """Publish metadata AFTER private storage and archive validation succeeded.

    The future upload endpoint must validate actual bytes, archive limits,
    symlinks, and manifest paths before invoking this internal helper.
    """
    project = Project.objects.select_for_update().get(pk=upload.project_id)
    token = AccessToken.objects.select_for_update().get(pk=token.pk)
    token = check_token_access(token, project, write=True)
    upload = ProjectUpload.objects.select_for_update().get(pk=upload.pk)
    if upload.status != ProjectUpload.Status.PENDING or upload.uploaded_by_id != token.user_id:
        raise ValidationError("Only the uploader can publish a pending upload.")
    now = timezone.now()
    upload.status = ProjectUpload.Status.READY
    upload.ready_at = now
    upload.full_clean()
    previous_id = project.current_upload_id
    upload.save(update_fields=["status", "ready_at"])
    project.current_upload = upload
    project.save(update_fields=["current_upload", "updated_at"])
    if previous_id:
        ProjectUpload.objects.filter(pk=previous_id).update(status=ProjectUpload.Status.SUPERSEDED)
    TransferEvent.objects.create(user=token.user, project=project, action=TransferEvent.Action.PUSH, outcome=TransferEvent.Outcome.ALLOWED, byte_count=upload.archive_size)
    return upload


@transaction.atomic
def issue_download_grant(token, upload, *, verification=None, risk_requires_verification=False):
    project = Project.objects.select_for_update().get(pk=upload.project_id)
    token = AccessToken.objects.select_for_update().get(pk=token.pk)
    check_token_access(token, project)
    upload = ProjectUpload.objects.get(pk=upload.pk)
    now = timezone.now()
    if project.current_upload_id != upload.pk or upload.status != ProjectUpload.Status.READY:
        raise PermissionDenied("Upload is not available.")
    if verification is not None:
        verification = VerificationRequest.objects.select_for_update().get(pk=verification.pk)
        if (
            verification.token_id != token.pk or verification.upload_id != upload.pk
            or verification.status != VerificationRequest.Status.APPROVED
            or verification.verified_at is None or verification.expires_at <= now
            or verification.consumed_at is not None
        ):
            raise PermissionDenied("Verification is invalid, expired, or already used.")
        verification.consumed_at = now
        verification.save(update_fields=["consumed_at"])
    elif project.require_download_verification or risk_requires_verification:
        raise PermissionDenied("Download verification is required.")
    secret = secrets.token_urlsafe(32)
    grant = DownloadGrant.objects.create(token=token, upload=upload, verification=verification, secret_hash=digest(secret), expires_at=now + timedelta(minutes=2))
    return grant, secret


@transaction.atomic
def consume_download_grant(secret, token):
    grant = DownloadGrant.objects.select_related("upload").filter(secret_hash=digest(secret), token_id=token.pk).first()
    if grant is None:
        raise PermissionDenied("Download grant is invalid.")
    project = Project.objects.select_for_update().get(pk=grant.upload.project_id)
    token = AccessToken.objects.select_for_update().get(pk=token.pk)
    check_token_access(token, project)
    upload = ProjectUpload.objects.get(pk=grant.upload_id)
    now = timezone.now()
    if project.current_upload_id != upload.pk or upload.status != ProjectUpload.Status.READY:
        raise PermissionDenied("Upload was replaced or is unavailable.")
    if project.require_download_verification and grant.verification_id is None:
        raise PermissionDenied("Download verification is required.")
    # Conditional update also prevents two consumers from redeeming one secret.
    consumed = DownloadGrant.objects.filter(pk=grant.pk, consumed_at__isnull=True, expires_at__gt=now).update(consumed_at=now)
    if consumed != 1:
        raise PermissionDenied("Download grant expired or was already used.")
    TransferEvent.objects.create(user=token.user, project=project, action=TransferEvent.Action.CLONE, outcome=TransferEvent.Outcome.ALLOWED, byte_count=upload.archive_size)
    return upload
