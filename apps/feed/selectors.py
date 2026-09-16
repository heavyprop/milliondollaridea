from apps.discussions.models import ThreadLike
from apps.discussions.selectors import threads_with_stats


def popular_threads(user):
    threads = threads_with_stats().order_by("-likes", "-created_at")

    liked_thread_ids = set(
        ThreadLike.objects.filter(user=user).values_list("thread_id", flat=True)
    )

    for thread in threads:
        thread.user_has_liked = thread.id in liked_thread_ids

    return threads
