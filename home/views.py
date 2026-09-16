from django.contrib.auth import logout
from django.db.models import Count, Q
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .models import Subject, Thread, ThreadLike
from .go_search import search_with_go
from .rate_limits import limit_requests
from .scoring import get_search_terms
from threads.label_classifier import get_top_labels
from threads.user_interests import build_user_interests


# view for boarding, new users
def boarding(request):
    return render(request, "home/boarding.html")

# view for the main homepage
def home(request):
    if not request.user.is_authenticated:
        return render(request, "home/boarding.html")

    threads = (
        Thread.objects
        .select_related("author", "subject")
        .annotate(
            comment_count=Count("comments", distinct=True),
            view_count=Count("thread_views", distinct=True),
        )
        .order_by("-likes", "-created_at")
    )

    liked_thread_ids = set(
        ThreadLike.objects
        .filter(user=request.user)
        .values_list("thread_id", flat=True)
    )

    for thread in threads:
        thread.user_has_liked = thread.id in liked_thread_ids

    user_interests = build_user_interests(request.user)
    
    subjects = Subject.objects.select_related("author").order_by("title")
    

    return render(request, "home/home.html", {
        "username": request.user.username,
        "threads": threads,
        "subjects": subjects,
        "user_interests": user_interests,
    })


@limit_requests(rate="8/m", group="search", method="GET", query_param="q")
def search(request):
    if not request.user.is_authenticated:
        return redirect("boarding")

    query = request.GET.get("q", "").strip()

    query_terms = []
    query_labels = []
    ranked_threads = []

    if query:
        query_terms = get_search_terms(query)
        query_labels = get_top_labels(query, None)
        result = search_with_go(query, query_labels)

        threads = (
            Thread.objects
            .select_related("author", "subject")
            .annotate(
                comment_count=Count("comments", distinct=True),
                view_count=Count("thread_views", distinct=True),
            )
        )

        if result is False:
            # Simple fallback: match any keyword, show the newest 50 threads.
            fallback_filter = Q()
            for term in query_terms or [query]:
                fallback_filter |= Q(title__icontains=term) | Q(description__icontains=term)
            ranked_threads = list(
                threads.filter(fallback_filter).order_by("-created_at", "-id")[:50]
            )
        else:
            query_terms = result["query_terms"]
            matches = result["results"]
            threads_by_id = threads.in_bulk([match["id"] for match in matches])

            # Preserve Go's ranking; skip threads deleted since its query.
            for match in matches:
                thread = threads_by_id.get(match["id"])
                if thread is not None:
                    thread.final_search_score = match["score"]
                    ranked_threads.append(thread)

    return render(request, "home/search.html", {
        "query": query,
        "query_terms": query_terms,
        "query_labels": query_labels,
        "search_results": ranked_threads,
    })

# view for the profile page
def profile(request):
    if not request.user.is_authenticated:
        return redirect("home")
    return render(request, "home/profile.html", {"username": request.user.username, 
                                            "date": request.user.date_joined})

@require_POST
def logout_view(request):
    logout(request)
    return redirect("boarding")
