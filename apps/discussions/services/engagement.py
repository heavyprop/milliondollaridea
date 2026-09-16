from django.db.models import F
from django.utils import timezone

from apps.discussions.models import Comment, CommentLike, Thread, ThreadLike, ThreadView


def record_view_time(thread_id, user, seconds):
    if seconds > 0:
        view, _ = ThreadView.objects.get_or_create(thread_id=thread_id, user=user)
        ThreadView.objects.filter(id=view.id).update(
            seconds=F("seconds") + min(seconds, 30),
            updated_at=timezone.now(),
        )


def add_thread_like(thread_id, user):
    _, created = ThreadLike.objects.get_or_create(thread_id=thread_id, user=user)
    if created:
        Thread.objects.filter(id=thread_id).update(likes=F("likes") + 1)
    thread = Thread.objects.get(id=thread_id)
    thread.user_has_liked = True
    return thread


def add_comment_like(comment_id, user):
    _, created = CommentLike.objects.get_or_create(comment_id=comment_id, user=user)
    if created:
        Comment.objects.filter(id=comment_id).update(likes=F("likes") + 1)
    comment = Comment.objects.get(id=comment_id)
    comment.user_has_liked = True
    return comment


def did_user_like(thread, user):
    thread.user_has_liked = ThreadLike.objects.filter(
        thread=thread,
        user=user,
    ).exists()
    return thread


def did_user_like_comments(comments, user):
    liked_comment_ids = set(
        CommentLike.objects.filter(user=user, comment__in=comments).values_list(
            "comment_id", flat=True
        )
    )

    for comment in comments:
        comment.user_has_liked = comment.id in liked_comment_ids

    return comments


def record_unique_thread_view(thread, user):
    view, created = ThreadView.objects.get_or_create(
        thread=thread,
        user=user,
    )

    if created:
        Thread.objects.filter(id=thread.id).update(views=F("views") + 1)

    return view
