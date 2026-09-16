from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST, require_http_methods
from django.http import Http404
from pathlib import PurePosixPath
import zipfile
import ipaddress
import shlex
from urllib.parse import urlsplit

from threads.templatetags.post_content import split_post_content

from .forms import TokenForm
from .models import AccessToken, Project, ProjectUpload
from .services import can_access, issue_token
from .storage import archive_path


@login_required(login_url="/accounts/")
@never_cache
def index(request):
    projects = (
        Project.objects.filter(Q(visibility=Project.Visibility.MEMBERS) | Q(owner=request.user) | Q(memberships__user=request.user))
        .select_related("owner", "current_upload")
        .distinct()
        .order_by("-updated_at", "id")
    )
    page = Paginator(projects, 20).get_page(request.GET.get("page"))
    return render(request, "hosting/index.html", {"page_obj": page})


@login_required(login_url="/accounts/")
@never_cache
def help_page(request):
    return render(request, "hosting/help.html", {
        "publish_blocks": [{"kind": "code", "language": "Terminal", "text": "safe publish ./my-project"}],
        "download_blocks": [{"kind": "code", "language": "Terminal", "text": "safe get username/project-name ./downloaded-project"}],
    })


@login_required(login_url="/accounts/")
@never_cache
@require_http_methods(["GET"])
def project_detail(request, owner, slug, file_id=None):
    project = get_object_or_404(Project.objects.select_related("owner", "current_upload"), owner__username=owner, slug=slug)
    if not can_access(request.user, project):
        raise Http404()
    upload = project.current_upload
    if upload is not None and upload.status != ProjectUpload.Status.READY:
        upload = None
    context = {"project": project, "upload": upload}
    if file_id is None:
        files = upload.files.all() if upload else []
        context["page_obj"] = Paginator(files, 100).get_page(request.GET.get("page"))
    else:
        if upload is None:
            raise Http404()
        file = get_object_or_404(upload.files, pk=file_id)
        context["file"] = file
        limit = 256 * 1024
        if project.require_download_verification:
            context["preview_message"] = "This project requires verification. File previews will be available when browser verification is enabled."
        elif file.size > limit:
            context["preview_message"] = "This file is too large to preview (256 KiB limit). Download the project with Safe CLI to view it."
        elif file.is_binary:
            context["preview_message"] = "This is a binary file. Download the project with Safe CLI to open it."
        else:
            try:
                with zipfile.ZipFile(archive_path(upload.storage_key)) as archive:
                    with archive.open(file.path) as stream:
                        data = stream.read(limit + 1)
                if len(data) > limit:
                    context["preview_message"] = "This file is too large to preview. Download the project with Safe CLI to view it."
                elif b"\x00" in data:
                    context["preview_message"] = "This is a binary file. Download the project with Safe CLI to open it."
                else:
                    content = data.decode("utf-8-sig")
                    extension = PurePosixPath(file.path).suffix.lower()
                    if extension in (".md", ".markdown"):
                        context["blocks"] = split_post_content(content)
                    else:
                        languages = {".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".tsx": "TSX", ".jsx": "JSX", ".html": "HTML", ".css": "CSS", ".json": "JSON", ".sh": "Shell", ".sql": "SQL", ".java": "Java", ".rs": "Rust", ".c": "C", ".cpp": "C++"}
                        context["blocks"] = [{"kind": "code", "language": languages.get(extension, "Text"), "text": content}]
                    if not content:
                        context["preview_message"] = "This file is empty."
            except UnicodeDecodeError:
                context["preview_message"] = "This file isn't UTF-8 text. Download the project with Safe CLI to open it."
            except (OSError, KeyError, zipfile.BadZipFile, RuntimeError):
                context["preview_message"] = "The stored file is currently unavailable."
                return render(request, "hosting/project_detail.html", context, status=503)
    return render(request, "hosting/project_detail.html", context)


@login_required(login_url="/accounts/")
@never_cache
@require_http_methods(["GET", "POST"])
def cli_access(request):
    form = TokenForm(request.POST if request.method == "POST" else None)
    secret = None
    created_token = None
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if AccessToken.objects.filter(user=user, revoked_at__isnull=True, expires_at__gt=timezone.now()).count() >= 10:
                form.add_error(None, "Revoke an existing token before creating another (limit: 10).")
            else:
                created_token, secret = issue_token(user, form.cleaned_data["name"], can_write=form.cleaned_data["can_write"])
                form = TokenForm()
    tokens = AccessToken.objects.filter(user=request.user, revoked_at__isnull=True, expires_at__gt=timezone.now()).order_by("-created_at")
    server_url = request.build_absolute_uri("/").rstrip("/")
    parsed = urlsplit(server_url)
    local = parsed.hostname == "localhost"
    try:
        local = local or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        pass
    login_command = f"safe login --server {shlex.quote(server_url)}"
    if parsed.scheme == "http" and not local:
        login_command += " --allow-http"
    return render(request, "hosting/cli_access.html", {
        "form": form, "token_secret": secret, "created_token": created_token,
        "tokens": tokens, "login_command": login_command,
        "get_command": f"safe get {shlex.quote(request.user.username + '/my-project')} ./downloaded-project",
    })


@login_required(login_url="/accounts/")
@require_POST
def revoke_token(request, token_id):
    token = get_object_or_404(AccessToken, pk=token_id, user=request.user)
    token.revoked_at = timezone.now()
    token.save(update_fields=["revoked_at"])
    return redirect("hosting:cli_access")
