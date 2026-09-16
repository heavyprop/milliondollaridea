from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.http import FileResponse, Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from safe_cli.archive import ArchiveError, MAX_ARCHIVE
from .models import Project, ProjectFile, ProjectUpload, TransferEvent
from .services import authenticate_token, can_access, check_token_access, consume_download_grant, issue_download_grant, publish_validated_upload
from .storage import archive_path, prepare_archive


class QuotaExceeded(Exception):
    pass


def endpoint(method):
    """Session cookies never authorize CLI endpoints; a bearer token is required."""
    def decorate(view):
        @csrf_exempt
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != method:
                response = JsonResponse({"error": f"Use {method}."}, status=405)
                response["Allow"] = method
            else:
                authorization = request.headers.get("Authorization", "")
                scheme, _, secret = authorization.partition(" ")
                try:
                    if scheme.lower() != "bearer" or not secret or len(secret) > 256:
                        raise PermissionDenied()
                    token = authenticate_token(secret)
                except PermissionDenied:
                    response = JsonResponse({"error": "Invalid or expired token. Run safe login."}, status=401)
                    response["WWW-Authenticate"] = "Bearer"
                else:
                    try:
                        response = view(request, token, *args, **kwargs)
                    except Http404:
                        response = JsonResponse({"error": "Project not found or access denied."}, status=404)
                    except PermissionDenied as exc:
                        response = JsonResponse({"error": str(exc) or "Access denied."}, status=403)
                    except (ArchiveError, ValidationError) as exc:
                        message = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
                        response = JsonResponse({"error": message}, status=400)
                    except QuotaExceeded as exc:
                        response = JsonResponse({"error": str(exc)}, status=429)
                        response["Retry-After"] = "3600"
            response["Cache-Control"] = "private, no-store"
            response["X-Content-Type-Options"] = "nosniff"
            return response
        return wrapped
    return decorate


def enforce_quota(user, action, size):
    """Caller holds the user row lock, shared across their tokens/projects."""
    now = timezone.now()
    allowed = TransferEvent.objects.filter(user=user, outcome=TransferEvent.Outcome.ALLOWED)
    if action == TransferEvent.Action.PUSH:
        count = allowed.filter(action=action, created_at__gte=now - timedelta(hours=1)).count()
        limit = getattr(settings, "HOSTING_PUBLISHES_PER_HOUR", 20)
    else:
        count = allowed.filter(action=action, created_at__gte=now - timedelta(days=1)).count()
        limit = getattr(settings, "HOSTING_DOWNLOADS_PER_DAY", 100)
    used_bytes = allowed.filter(created_at__gte=now - timedelta(days=1)).aggregate(total=Sum("byte_count"))["total"] or 0
    if count >= limit or used_bytes + size > getattr(settings, "HOSTING_TRANSFER_BYTES_PER_DAY", 1024 ** 3):
        raise QuotaExceeded("Transfer limit reached. Try again later.")


@endpoint("GET")
def me(request, token):
    return JsonResponse({"username": token.user.get_username(), "can_publish": token.can_write})


@endpoint("POST")
def publish(request, token, owner, slug):
    # Authorization precedes parsing or saving uploaded bytes.
    project = Project.objects.filter(owner__username=owner, slug=slug).first()
    if project:
        if not can_access(token.user, project):
            raise Http404()
        check_token_access(token, project, write=True)
    elif owner != token.user.get_username() or not token.can_write:
        raise Http404()
    try:
        content_length = int(request.headers.get("Content-Length", "0"))
    except ValueError:
        return JsonResponse({"error": "Invalid Content-Length."}, status=400)
    if content_length <= 0:
        return JsonResponse({"error": "Content-Length is required."}, status=411)
    if content_length > getattr(settings, "HOSTING_MAX_ARCHIVE_BYTES", MAX_ARCHIVE) + 256 * 1024:
        return JsonResponse({"error": "Upload exceeds the archive size limit."}, status=413)
    if set(request.FILES) != {"archive"} or len(request.FILES.getlist("archive")) != 1:
        raise ValidationError("Upload exactly one ZIP in the archive field.")
    key, size, unpacked, sha256, records = prepare_archive(request.FILES["archive"])
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
                if Project.objects.filter(owner=user).count() >= getattr(settings, "HOSTING_PROJECTS_PER_USER", 100):
                    raise QuotaExceeded("Project limit reached.")
                project = Project(owner=user, name=slug, slug=slug)
                project.full_clean()
                project.save()
            check_token_access(token, project, write=True)
            upload = ProjectUpload.objects.create(
                project=project, uploaded_by=user, storage_key=key,
                original_filename="project.zip", sha256=sha256,
                archive_size=size, unpacked_size=unpacked, file_count=len(records),
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
    return JsonResponse({"project": f"{owner}/{slug}", "files": len(records), "bytes": size, "sha256": sha256}, status=201)


@endpoint("GET")
def download(request, token, owner, slug):
    stream = None
    try:
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=token.user_id)
            project = Project.objects.select_for_update().filter(owner__username=owner, slug=slug).first()
            if project is None or not can_access(user, project):
                raise Http404()
            check_token_access(token, project)
            upload = project.current_upload
            if upload is None or upload.status != ProjectUpload.Status.READY:
                return JsonResponse({"error": "This project has no published files."}, status=404)
            if project.require_download_verification:
                raise PermissionDenied("This project requires verification. Browser challenge integration is not available in this CLI version.")
            enforce_quota(user, TransferEvent.Action.CLONE, upload.archive_size)
            try:
                stream = archive_path(upload.storage_key).open("rb")
            except FileNotFoundError:
                return JsonResponse({"error": "Stored archive is unavailable."}, status=503)
            _, secret = issue_download_grant(token, upload)
            consume_download_grant(secret, token)
        response = FileResponse(stream, as_attachment=True, filename=f"{slug}.zip", content_type="application/zip")
        response["X-Archive-SHA256"] = upload.sha256
        return response
    except Exception:
        if stream:
            stream.close()
        raise
