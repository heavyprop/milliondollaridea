from django.contrib.auth.decorators import login_required
from django.db.models import F
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from home.models import Comment, CommentLike, Subject, Thread, ThreadLike, ThreadView
from home.rate_limits import limit_requests
from .label_classifier import get_top_labels

# creating a thread, then passing to ML model -> label_classifier def get_top_labels to classify the post
@login_required
@limit_requests(rate="2/m", group="create_thread")
def create_thread(request):
    subjects = Subject.objects.order_by("title")

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "")
        subject_id = request.POST.get("subject")
        subject = get_object_or_404(Subject, id=subject_id) if subject_id else None

        if title and description.strip():
            # ML CLASSIFIER
            topic_labels = get_top_labels(title, description)

            # Create the thread
            Thread.objects.create(
                author=request.user,
                title=title,
                description=description,
                subject=subject,
                topic_labels=topic_labels,
            )
            return redirect("home")

    return render(request, "threads/create_thread.html", {"subjects": subjects})

@login_required
@limit_requests(rate="2/m", group="create_subject")
def create_subject(request):
    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        description = request.POST.get("description", "")

        if title and description.strip():
            if Subject.objects.filter(title__iexact=title).exists():
                return render(request, "threads/create_subject.html", {
                    "error": "A subject with that title already exists."
                })

            Subject.objects.create(
            author=request.user,
            title=title,
            description=description,
        )
        return redirect("home")
    return render(request, "threads/create_subject.html")

@login_required
def subject_detail(request, subject_id):
    subject = get_object_or_404(Subject.objects.select_related("author"), id=subject_id)
    threads = subject.threads.select_related("author").order_by("-created_at")
    return render(request, "threads/subject_detail.html", {
        "subject": subject,
        "threads": threads,
    })



# checking if user liked the post
# helper function
def did_user_like(thread, user):
    thread.user_has_liked = ThreadLike.objects.filter(
        thread=thread,
        user=user,
    ).exists()
    return thread


def did_user_like_comments(comments, user):
    liked_comment_ids = set(
        CommentLike.objects
        .filter(user=user, comment__in=comments)
        .values_list("comment_id", flat=True)
    )

    for comment in comments:
        comment.user_has_liked = comment.id in liked_comment_ids

    return comments


def build_comment_tree(comments):
    comments_by_parent = {}

    for comment in comments:
        comment.children = []
        comments_by_parent.setdefault(comment.parent_id, []).append(comment)

    for comment in comments:
        comment.children = comments_by_parent.get(comment.id, [])

    return comments_by_parent.get(None, [])


def record_unique_thread_view(thread, user):
    view, created = ThreadView.objects.get_or_create(
        thread=thread,
        user=user,
    )

    if created:
        Thread.objects.filter(id=thread.id).update(views=F("views") + 1)

    return view

# opening the thread details
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
    comments = list(
        thread.comments
        .select_related("author")
        .order_by("created_at")
    )
    did_user_like_comments(comments, request.user)
    top_level_comments = build_comment_tree(comments)

    return render(request, "threads/detail.html", {
        "thread": thread,
        "comments": top_level_comments,
    })


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


@login_required
@require_POST
def record_thread_view(request, thread_id):
    seconds = int(request.POST.get("seconds", 0))

    if seconds > 0:
        view, created = ThreadView.objects.get_or_create(
            thread_id=thread_id,
            user=request.user,
        )

        ThreadView.objects.filter(id=view.id).update(
            seconds=F("seconds") + min(seconds, 30),
            updated_at=timezone.now(),
        )

    return render(request, "threads/partials/empty.html")


@login_required
@require_POST
@limit_requests(rate="20/m", group="likes")
def like_thread(request, thread_id):
    like, created = ThreadLike.objects.get_or_create(
        thread_id=thread_id,
        user=request.user,
    )

    if created:
        Thread.objects.filter(id=thread_id).update(likes=F("likes") + 1)

    thread = Thread.objects.get(id=thread_id)
    thread.user_has_liked = True

    return render(request, "threads/partials/like_button.html", {
        "thread": thread,
    })


@login_required
@require_POST
@limit_requests(rate="25/m", group="likes")
def like_comment(request, comment_id):
    like, created = CommentLike.objects.get_or_create(
        comment_id=comment_id,
        user=request.user,
    )

    if created:
        Comment.objects.filter(id=comment_id).update(likes=F("likes") + 1)

    comment = Comment.objects.get(id=comment_id)
    comment.user_has_liked = True

    return render(request, "threads/partials/comment_like_button.html", {
        "comment": comment,
    })
