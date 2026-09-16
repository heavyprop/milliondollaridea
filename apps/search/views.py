from django.shortcuts import redirect, render

from apps.search.services import search_threads
from common.security.rate_limits import limit_requests


@limit_requests(rate="8/m", group="search", method="GET", query_param="q")
def search(request):
    if not request.user.is_authenticated:
        return redirect("boarding")

    query = request.GET.get("q", "").strip()

    query_terms, query_labels, ranked_threads = search_threads(query)

    return render(
        request,
        "search/results.html",
        {
            "query": query,
            "query_terms": query_terms,
            "query_labels": query_labels,
            "search_results": ranked_threads,
        },
    )
