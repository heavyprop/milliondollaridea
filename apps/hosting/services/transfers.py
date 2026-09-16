"""Archive transfer transactions, independent of request parsing and responses."""

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404

from apps.hosting.models import Project, ProjectFile, ProjectUpload, TransferEvent
from apps.hosting.storage import archive_path, prepare_archive

from .access import can_access
from .downloads import consume_download_grant, issue_download_grant
from .quotas import QuotaExceeded, enforce_quota
from .tokens import check_token_access
from .uploads import publish_validated_upload


class DownloadUnavailable(Exception):
    def __init__(self, message, *, status):
        super().__init__(message)
        self.status = status


def authorize_publish(token, owner, slug):
    project = Project.objects.filter(owner__username=owner, slug=slug).first()
    if project:
        if not can_access(token.user, project):
            raise Http404()
        check_token_access(token, project, write=True)
    elif owner != token.user.get_username() or not token.can_write:
        raise Http404()


def publish_archive(token, owner, slug, archive):
    authorize_publish(token, owner, slug)
    key, size, unpacked, sha256, records = prepare_archive(archive)
    committed = False
    try:
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=token.user_id)
            if not user.is_active:
                raise PermissionDenied("Account is inactive.")
            enforce_quota(user, TransferEvent.Action.PUSH, size)
            project = Project.objects.filter(owner__username=owner, slug=slug).first()
            if project is None:
                # This request can create projects only for the token owner.
                if owner != user.get_username() or not token.can_write:
                    raise Http404()
                if Project.objects.filter(owner=user).count() >= getattr(
                    settings, "HOSTING_PROJECTS_PER_USER", 100
                ):
                    raise QuotaExceeded("Project limit reached.")
                project = Project(owner=user, name=slug, slug=slug)
                project.full_clean()
                project.save()
            check_token_access(token, project, write=True)
            upload = ProjectUpload.objects.create(
                project=project,
                uploaded_by=user,
                storage_key=key,
                original_filename="project.zip",
                sha256=sha256,
                archive_size=size,
                unpacked_size=unpacked,
                file_count=len(records),
            )
            files = [ProjectFile(upload=upload, **record) for record in records]
            for file in files:
                file.full_clean(validate_unique=False, validate_constraints=False)
            ProjectFile.objects.bulk_create(files)
            publish_validated_upload(upload, token)
        committed = True
    finally:
        if not committed:
            archive_path(key).unlink(missing_ok=True)
    return {
        "project": f"{owner}/{slug}",
        "files": len(records),
        "bytes": size,
        "sha256": sha256,
    }


def open_download(token, owner, slug):
    stream = None
    try:
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=token.user_id)
            project = (
                Project.objects.select_for_update()
                .filter(owner__username=owner, slug=slug)
                .first()
            )
            if project is None or not can_access(user, project):
                raise Http404()
            check_token_access(token, project)
            upload = project.current_upload
            if upload is None or upload.status != ProjectUpload.Status.READY:
                raise DownloadUnavailable(
                    "This project has no published files.", status=404
                )
            if project.require_download_verification:
                raise PermissionDenied(
                    "This project requires verification. Browser challenge integration is not available in this CLI version."
                )
            enforce_quota(user, TransferEvent.Action.CLONE, upload.archive_size)
            try:
                stream = archive_path(upload.storage_key).open("rb")
            except FileNotFoundError:
                raise DownloadUnavailable(
                    "Stored archive is unavailable.", status=503
                ) from None
            _, secret = issue_download_grant(token, upload)
            consume_download_grant(secret, token)
        return stream, upload
    except Exception:
        if stream:
            stream.close()
        raise
