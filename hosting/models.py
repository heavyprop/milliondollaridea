"""Private file-hosting records. Upload generations are not Git history."""

import uuid
from pathlib import PurePosixPath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import F, Q
from django.db.models.functions import Lower


sha256_validator = RegexValidator(r"\A[0-9a-f]{64}\Z", "Enter a lowercase SHA-256 digest.")
slug_validator = RegexValidator(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z", "Use lowercase letters, numbers, and single hyphens.")


def validate_project_path(value):
    """Paths are portable, relative POSIX paths, never filesystem locations."""
    path = PurePosixPath(value)
    if (
        not value or path.is_absolute() or "\\" in value or ":" in value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
        or any(part in ("", ".", "..") for part in value.split("/"))
    ):
        raise ValidationError("Use a relative file path without traversal or empty segments.")


class Project(models.Model):
    class Visibility(models.TextChoices):
        PRIVATE = "private", "Private"
        MEMBERS = "members", "Signed-in members"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosted_projects")
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=80, validators=[slug_validator])
    description = models.TextField(blank=True, max_length=2000)
    visibility = models.CharField(max_length=10, choices=Visibility, default=Visibility.MEMBERS)
    is_archived = models.BooleanField(default=False)
    require_download_verification = models.BooleanField(default=False)
    current_upload = models.OneToOneField("ProjectUpload", null=True, blank=True, on_delete=models.SET_NULL, related_name="current_for_project")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [models.UniqueConstraint(Lower("slug"), F("owner"), name="hosting_owner_slug_unique")]

    def clean(self):
        super().clean()
        if self.current_upload_id:
            upload = self.current_upload
            if upload.project_id != self.pk or upload.status != ProjectUpload.Status.READY:
                raise ValidationError({"current_upload": "The current upload must be ready and belong to this project."})

    def __str__(self):
        return self.name


class ProjectMembership(models.Model):
    class Role(models.TextChoices):
        READER = "reader", "Can download"
        WRITER = "writer", "Can upload and download"

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosting_memberships")
    role = models.CharField(max_length=10, choices=Role, default=Role.READER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["project", "user"], name="hosting_member_unique")]


class ProjectUpload(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending validation"
        READY = "ready", "Ready"
        FAILED = "failed", "Failed"
        SUPERSEDED = "superseded", "Replaced; awaiting cleanup"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="uploads")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="hosting_uploads")
    status = models.CharField(max_length=12, choices=Status, default=Status.PENDING)
    # An opaque key in PRIVATE storage; never a publicly served MEDIA_URL.
    storage_key = models.CharField(max_length=255, unique=True, default=uuid.uuid4, editable=False)
    original_filename = models.CharField(max_length=255, blank=True)
    sha256 = models.CharField(max_length=64, blank=True, validators=[sha256_validator])
    archive_size = models.PositiveBigIntegerField(default=0)
    unpacked_size = models.PositiveBigIntegerField(default=0)
    file_count = models.PositiveIntegerField(default=0)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    ready_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["project", "status"], name="hosting_upload_status_idx")]
        constraints = [models.CheckConstraint(condition=~Q(status="ready") | (Q(ready_at__isnull=False) & ~Q(sha256="")), name="hosting_ready_metadata")]


class ProjectFile(models.Model):
    upload = models.ForeignKey(ProjectUpload, on_delete=models.CASCADE, related_name="files")
    path = models.CharField(max_length=1024, validators=[validate_project_path])
    size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64, validators=[sha256_validator])
    content_type = models.CharField(max_length=127, default="application/octet-stream")
    is_binary = models.BooleanField(default=True)

    class Meta:
        ordering = ["path"]
        constraints = [models.UniqueConstraint(fields=["upload", "path"], name="hosting_file_path_unique")]


class AccessToken(models.Model):
    """Store only a digest. The random bearer secret is returned once."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="hosting_tokens")
    name = models.CharField(max_length=100)
    token_hash = models.CharField(max_length=64, unique=True, validators=[sha256_validator], editable=False)
    can_write = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    revoked_at = models.DateTimeField(null=True, blank=True)
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(expires_at__gt=F("created_at")), name="hosting_token_expiry")]


class VerificationRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DENIED = "denied", "Denied"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey(AccessToken, on_delete=models.CASCADE, related_name="verifications")
    upload = models.ForeignKey(ProjectUpload, on_delete=models.CASCADE, related_name="verifications")
    code_hash = models.CharField(max_length=64, unique=True, validators=[sha256_validator], editable=False)
    status = models.CharField(max_length=10, choices=Status, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(expires_at__gt=F("created_at")), name="hosting_verify_expiry"),
            models.CheckConstraint(condition=~Q(status="approved") | Q(verified_at__isnull=False), name="hosting_verify_approved"),
        ]


class DownloadGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.ForeignKey(AccessToken, on_delete=models.CASCADE, related_name="download_grants")
    upload = models.ForeignKey(ProjectUpload, on_delete=models.CASCADE, related_name="download_grants")
    verification = models.OneToOneField(VerificationRequest, null=True, blank=True, on_delete=models.CASCADE, related_name="download_grant")
    secret_hash = models.CharField(max_length=64, unique=True, validators=[sha256_validator], editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(expires_at__gt=F("created_at")), name="hosting_grant_expiry")]

    def clean(self):
        super().clean()
        if self.verification_id:
            verification = self.verification
            if verification.token_id != self.token_id or verification.upload_id != self.upload_id:
                raise ValidationError({"verification": "Verification must match the token and upload."})


class TransferEvent(models.Model):
    class Action(models.TextChoices):
        PUSH = "push", "Upload"
        CLONE = "clone", "Download"

    class Outcome(models.TextChoices):
        ALLOWED = "allowed", "Allowed"
        DENIED = "denied", "Denied"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="hosting_events")
    project = models.ForeignKey(Project, null=True, on_delete=models.SET_NULL, related_name="transfer_events")
    action = models.CharField(max_length=8, choices=Action)
    outcome = models.CharField(max_length=8, choices=Outcome)
    byte_count = models.PositiveBigIntegerField(default=0)
    reason = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["user", "action", "created_at"], name="hosting_event_usage_idx")]
