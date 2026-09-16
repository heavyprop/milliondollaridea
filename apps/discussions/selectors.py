"""Read-only discussion queries shared by pages, feed, and search."""

from django.db.models import Count

from .models import Subject, Thread
from .services.comments import build_comment_tree
from .services.engagement import did_user_like_comments


def threads_with_stats():
    return Thread.objects.select_related("author", "subject").annotate(
        comment_count=Count("comments", distinct=True),
        view_count=Count("thread_views", distinct=True),
    )


def subjects_by_title():
    return Subject.objects.select_related("author").order_by("title")


def comment_tree_for_user(thread, user):
    comments = list(thread.comments.select_related("author").order_by("created_at"))
    did_user_like_comments(comments, user)
    return build_comment_tree(comments)
