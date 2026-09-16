from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.discussions.models import Subject, Thread, ThreadView
from apps.discussions.selectors import comment_tree_for_user, subjects_by_title
from apps.discussions.services.engagement import (
    did_user_like,
    record_unique_thread_view,
)
from apps.discussions.services.posts import create_post
from common.security.rate_limits import limit_requests


@login_required
@limit_requests(rate="2/m", group="create_thread")
def create_thread(request):
    subjects = subjects_by_title()

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "")
        subject_id = request.POST.get("subject")
        subject = get_object_or_404(Subject, id=subject_id) if subject_id else None

        if title and description.strip():
            create_post(
                author=request.user,
                title=title,
                description=description,
                subject=subject,
            )
            return redirect("home")

    return render(request, "discussions/create_thread.html", {"subjects": subjects})

@login_required
@limit_requests(rate="1/m", group="delete_thread", method="GET")
def delete_thread(request, thread_id):
    if request.method == "POST":
        thread = get_object_or_404(Thread, id=thread_id, author=request.user)

        thread.delete()
        return redirect("home")


@login_required
@limit_requests(rate="8/m", group="thread_detail", method="GET")
def thread_detail(request, thread_id):
    thread = get_object_or_404(
        Thread.objects.select_related("author", "subject"),
        id=thread_id,
    )

    record_unique_thread_view(thread, request.user)
    thread.view_count = ThreadView.objects.filter(thread=thread).count()
    did_user_like(thread, request.user)
    top_level_comments = comment_tree_for_user(thread, request.user)

    return render(
        request,
        "discussions/detail.html",
        {
            "thread": thread,
            "comments": top_level_comments,
            "is_user": thread.author == request.user,
        },
    )
