from apps.discussions.models import Comment, ThreadLike


def users_notifications(user):
    likes = (
        ThreadLike.objects.filter(thread__author=user)
        .exclude(user=user)
        .select_related("user", "thread")
        .order_by("-created_at", "-pk")[:50]
    )

    comments = (
        Comment.objects.filter(thread__author=user)
        .exclude(author=user)
        .select_related("author", "thread")
        .order_by("-created_at", "-pk")[:50]
    )

    notifications = [
        {
            "type": "like",
            "actor": like.user,
            "thread": like.thread,
            "created_at": like.created_at,
        }
        for like in likes
    ]

    notifications.extend(
        {
            "type": "comment",
            "actor": comment.author,
            "thread": comment.thread,
            "comment": comment,
            "created_at": comment.created_at,
        }
        for comment in comments
    )

    notifications.sort(
        key=lambda notification: notification["created_at"],
        reverse=True,
    )

    return notifications[:50]
