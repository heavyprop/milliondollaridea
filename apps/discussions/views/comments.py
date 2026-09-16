from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST

from apps.discussions.models import Comment, Thread
from common.security.rate_limits import limit_requests


@login_required
@require_POST
@limit_requests(rate="10/m", group="create_comment")
def create_comment(request, thread_id):
    thread = get_object_or_404(Thread, id=thread_id)
    body = request.POST.get("body", "")
    parent_id = request.POST.get("parent_id")
    parent = None

    if parent_id:
        parent = get_object_or_404(Comment, id=parent_id, thread=thread)

    if body.strip():
        Comment.objects.create(
            thread=thread,
            parent=parent,
            author=request.user,
            body=body,
        )

    return redirect("thread_detail", thread_id=thread.id)
