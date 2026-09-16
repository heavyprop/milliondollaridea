import json
import logging
import math
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)

def search_with_go(query, labels):
    """Return ranked results, or False when Go cannot provide a valid response."""
    try:
        request = Request(
            getattr(settings, "GO_SEARCH_URL", "http://127.0.0.1:8080/search"),
            data=json.dumps({"query": query, "labels": labels}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=20) as response:
            result = json.load(response)

        if not isinstance(result, dict):
            raise ValueError("Expected a search response object")
        terms = result.get("query_terms")
        matches = result.get("results")
        if not isinstance(terms, list) or not all(isinstance(term, str) for term in terms):
            raise ValueError("Invalid query terms")
        if not isinstance(matches, list):
            raise ValueError("Invalid search results")
        for match in matches:
            if (
                not isinstance(match, dict)
                or type(match.get("id")) is not int
                or type(match.get("score")) not in (int, float)
                or not math.isfinite(match["score"])
            ):
                raise ValueError("Invalid search result")
        return result
    except (URLError, OSError, ValueError):
        logger.exception("Go search unavailable; using Django search")
        return False
