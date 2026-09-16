from apps.discussions.models import Comment, CommentLike, Thread, ThreadLike, ThreadView

FORGETTING_FACTOR = 0.95
MAX_EVENTS = 200
MAX_TAGS = 100

VIEW_WEIGHT = 0.25
COMMENT_LIKE_WEIGHT = 1.0
THREAD_LIKE_WEIGHT = 3.0
COMMENT_WEIGHT = 4.0
CREATED_THREAD_WEIGHT = 5.0


def get_view_weight(seconds):
    return VIEW_WEIGHT * min(seconds / 30, 2)


def add_thread_tags(user_interests, thread, weight):
    for tag in thread.topic_labels or []:
        tag_id = tag["id"]

        if tag_id not in user_interests:
            user_interests[tag_id] = {
                "label": tag["label"],
                "weight": 0,
            }

        user_interests[tag_id]["weight"] += tag["score"] * weight


def collect_user_events(user):
    events = []

    for view in ThreadView.objects.select_related("thread").filter(user=user):
        events.append(
            {
                "created_at": view.updated_at,
                "thread": view.thread,
                "weight": get_view_weight(view.seconds),
                "type": "view_post",
            }
        )

    for comment_like in CommentLike.objects.select_related("comment__thread").filter(
        user=user
    ):
        events.append(
            {
                "created_at": comment_like.created_at,
                "thread": comment_like.comment.thread,
                "weight": COMMENT_LIKE_WEIGHT,
                "type": "like_comment",
            }
        )

    for thread_like in ThreadLike.objects.select_related("thread").filter(user=user):
        events.append(
            {
                "created_at": thread_like.created_at,
                "thread": thread_like.thread,
                "weight": THREAD_LIKE_WEIGHT,
                "type": "like_post",
            }
        )

    for comment in Comment.objects.select_related("thread").filter(author=user):
        events.append(
            {
                "created_at": comment.created_at,
                "thread": comment.thread,
                "weight": COMMENT_WEIGHT,
                "type": "comment_on_post",
            }
        )

    for thread in Thread.objects.filter(author=user):
        events.append(
            {
                "created_at": thread.created_at,
                "thread": thread,
                "weight": CREATED_THREAD_WEIGHT,
                "type": "create_post",
            }
        )

    return sorted(events, key=lambda event: event["created_at"], reverse=True)[
        :MAX_EVENTS
    ]


def build_user_interests(user):
    user_interests = {}
    events = collect_user_events(user)

    for steps_ago, event in enumerate(events):
        decay = FORGETTING_FACTOR**steps_ago
        weight = event["weight"] * decay
        add_thread_tags(user_interests, event["thread"], weight)

    ranked = sorted(
        user_interests.items(),
        key=lambda item: item[1]["weight"],
        reverse=True,
    )

    return dict(ranked[:MAX_TAGS])


def print_user_interests(user):
    interests = build_user_interests(user)

    for tag_id, data in interests.items():
        print(f"{tag_id}: {data['label']} = {data['weight']:.4f}")
