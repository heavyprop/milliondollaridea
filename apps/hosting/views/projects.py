from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.hosting.models import Project, ProjectUpload
from apps.hosting.services.access import can_access
from apps.hosting.services.previews import file_preview


@login_required(login_url="/accounts/")
@never_cache
def index(request):
    projects = (
        Project.objects.filter(
            Q(visibility=Project.Visibility.MEMBERS)
            | Q(owner=request.user)
            | Q(memberships__user=request.user)
        )
        .select_related("owner", "current_upload")
        .distinct()
        .order_by("-updated_at", "id")
    )
    page = Paginator(projects, 20).get_page(request.GET.get("page"))
    return render(request, "hosting/index.html", {"page_obj": page})


@login_required(login_url="/accounts/")
@never_cache
@require_http_methods(["GET"])
def project_detail(request, owner, slug, file_id=None):
    project = get_object_or_404(
        Project.objects.select_related("owner", "current_upload"),
        owner__username=owner,
        slug=slug,
    )
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
        preview, status = file_preview(project, upload, file)
        context.update(preview)
        return render(request, "hosting/project_detail.html", context, status=status)
    return render(request, "hosting/project_detail.html", context)
