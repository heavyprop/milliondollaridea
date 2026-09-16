"""Search workflow: classify, call Go, then hydrate or fall back to keywords."""

from apps.recommendations.classification import get_top_labels

from .client import search_with_go
from .fallback import keyword_search
from .selectors import hydrate_ranked_posts


def search_threads(query):
    if not query:
        return [], [], []
    query_labels = get_top_labels(query, None)
    result = search_with_go(query, query_labels)
    if result is False:
        query_terms, posts = keyword_search(query)
    else:
        query_terms = result["query_terms"]
        posts = hydrate_ranked_posts(result["results"])
    return query_terms, query_labels, posts
