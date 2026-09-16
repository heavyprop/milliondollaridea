from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.discussions.models import Subject
from common.security.rate_limits import limit_requests


@login_required
@limit_requests(rate="2/m", group="create_subject")
def create_subject(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "")

        if title and description.strip():
            if Subject.objects.filter(title__iexact=title).exists():
                return render(
                    request,
                    "discussions/create_subject.html",
                    {"error": "A subject with that title already exists."},
                )

            Subject.objects.create(
                author=request.user,
                title=title,
                description=description,
            )
        return redirect("home")
    return render(request, "discussions/create_subject.html")


@login_required
def subject_detail(request, subject_id):
    subject = get_object_or_404(Subject.objects.select_related("author"), id=subject_id)
    threads = subject.threads.select_related("author").order_by("-created_at")
    return render(
        request,
        "discussions/subject_detail.html",
        {
            "subject": subject,
            "threads": threads,
        },
    )
