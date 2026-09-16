from django.shortcuts import render

from apps.discussions.selectors import subjects_by_title
from apps.feed.selectors import popular_threads
from apps.recommendations.interests import build_user_interests


def home(request):
    if not request.user.is_authenticated:
        return render(request, "feed/boarding.html")

    threads = popular_threads(request.user)

    user_interests = build_user_interests(request.user)

    subjects = subjects_by_title()

    return render(
        request,
        "feed/index.html",
        {
            "username": request.user.username,
            "threads": threads,
            "subjects": subjects,
            "user_interests": user_interests,
        },
    )
