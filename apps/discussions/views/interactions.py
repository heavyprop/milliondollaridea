"""HTMX endpoints; persistence lives in the engagement service."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.views.decorators.http import require_POST

from apps.discussions.services.engagement import (
    add_comment_like,
    add_thread_like,
    record_view_time,
)
from common.security.rate_limits import limit_requests


@login_required
@require_POST
def record_thread_view(request, thread_id):
    seconds = int(request.POST.get("seconds", 0))
    record_view_time(thread_id, request.user, seconds)
    return render(request, "discussions/partials/empty.html")


@login_required
@require_POST
@limit_requests(rate="20/m", group="likes")
def like_thread(request, thread_id):
    thread = add_thread_like(thread_id, request.user)
    return render(request, "discussions/partials/like_button.html", {"thread": thread})


@login_required
@require_POST
@limit_requests(rate="25/m", group="likes")
def like_comment(request, comment_id):
    comment = add_comment_like(comment_id, request.user)
    return render(
        request, "discussions/partials/comment_like_button.html", {"comment": comment}
    )
