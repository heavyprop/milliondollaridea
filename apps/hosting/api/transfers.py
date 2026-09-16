"""CLI transfer HTTP endpoints; archive transactions live in services."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.http import FileResponse, JsonResponse

from apps.hosting.services.transfers import (
    DownloadUnavailable,
    authorize_publish,
    open_download,
    publish_archive,
)
from safe_cli.archive import MAX_ARCHIVE

from .decorators import endpoint


@endpoint("POST")
def publish(request, token, owner, slug):
    # Check access before request.FILES triggers multipart parsing.
    authorize_publish(token, owner, slug)
    try:
        content_length = int(request.headers.get("Content-Length", "0"))
    except ValueError:
        return JsonResponse({"error": "Invalid Content-Length."}, status=400)
    if content_length <= 0:
        return JsonResponse({"error": "Content-Length is required."}, status=411)
    if (
        content_length
        > getattr(settings, "HOSTING_MAX_ARCHIVE_BYTES", MAX_ARCHIVE) + 256 * 1024
    ):
        return JsonResponse(
            {"error": "Upload exceeds the archive size limit."}, status=413
        )
    if set(request.FILES) != {"archive"} or len(request.FILES.getlist("archive")) != 1:
        raise ValidationError("Upload exactly one ZIP in the archive field.")
    result = publish_archive(token, owner, slug, request.FILES["archive"])
    return JsonResponse(result, status=201)


@endpoint("GET")
def download(request, token, owner, slug):
    try:
        stream, upload = open_download(token, owner, slug)
    except DownloadUnavailable as exc:
        return JsonResponse({"error": str(exc)}, status=exc.status)
    try:
        response = FileResponse(
            stream,
            as_attachment=True,
            filename=f"{slug}.zip",
            content_type="application/zip",
        )
        response["X-Archive-SHA256"] = upload.sha256
        return response
    except Exception:
        stream.close()
        raise
