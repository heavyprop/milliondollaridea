from apps.accounts.models import UserBlock
from apps.discussions.models import ThreadLike
from apps.discussions.selectors import threads_with_stats


def popular_threads(user):
    blocked_user_ids = UserBlock.objects.filter(blocker=user).values_list(
        "blocked_id", flat=True
    )
    threads = (
        threads_with_stats()
        .exclude(author=user)
        .exclude(author_id__in=blocked_user_ids)
        .order_by("-likes", "-created_at")
    )

    liked_thread_ids = set(
        ThreadLike.objects.filter(user=user).values_list("thread_id", flat=True)
    )

    for thread in threads:
        thread.user_has_liked = thread.id in liked_thread_ids

    return threads

def users_threads(user):
    threads = (
        threads_with_stats()
        .filter(author=user)
        .order_by("-created_at")
    )

    return threads
