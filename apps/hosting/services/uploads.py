from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.hosting.models import AccessToken, Project, ProjectUpload, TransferEvent

from .tokens import check_token_access


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
    if (
        upload.status != ProjectUpload.Status.PENDING
        or upload.uploaded_by_id != token.user_id
    ):
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
        ProjectUpload.objects.filter(pk=previous_id).update(
            status=ProjectUpload.Status.SUPERSEDED
        )
    TransferEvent.objects.create(
        user=token.user,
        project=project,
        action=TransferEvent.Action.PUSH,
        outcome=TransferEvent.Outcome.ALLOWED,
        byte_count=upload.archive_size,
    )
    return upload
