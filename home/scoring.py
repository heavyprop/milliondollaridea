# this is for the search algorithm 
import math
import re
from statistics import median

from django.db.models import Q
from django.utils import timezone

# stop words to remove the non important words 

STOP_WORDS = { "a", "an", "and", "are", "as", "at", "be", "best", "but", "by", "for", "from", "has", "have", "how", "i", "if", "in", "is", "it", "of", "on", "or", "should", "that", "the", "this", "to", "was", "what", "when", "where", "which", "who", "why", "with", "you", } 

TOKEN_RE = re.compile(r"[a-z0-9+#.]+") 

RECENCY_HALF_LIFE_DAYS = 14
TITLE_TEXT_WEIGHT = 0.70 
DESCRIPTION_TEXT_WEIGHT = 0.30 
TEXT_RELEVANCE_WEIGHT = 0.65
TAG_RELEVANCE_WEIGHT = 0.35
AGREEMENT_BONUS_WEIGHT = 0.30

LIKE_ENGAGEMENT_WEIGHT = 0.55
COMMENT_ENGAGEMENT_WEIGHT = 0.30
VIEW_ENGAGEMENT_WEIGHT = 0.15

FINAL_RELEVANCE_WEIGHT = 0.70
FINAL_RECENCY_WEIGHT = 0.30

MIN_RELEVANCE_SCORE = 0.05
MIN_TAG_MATCH_SCORE = 0.10
ALLOW_ANY_TEXT_MATCH = True
MIN_POPULARITY_FACTOR = 0.30


def get_search_terms(query):
    terms = []

    for term in TOKEN_RE.findall(query.lower()):
        if len(term) >= 2 and term not in STOP_WORDS:
            terms.append(term)

    return list(dict.fromkeys(terms))

def build_candidate_filter(query_terms, query_labels):
    candidate_filter = Q()

    for term in query_terms:
        candidate_filter |= Q(title__icontains=term)
        candidate_filter |= Q(description__icontains=term)

    for label in query_labels:
        candidate_filter |= Q(topic_labels__contains=[{"id": label["id"]}])

    return candidate_filter


def get_text_match_score(query_terms, text):
    if not query_terms:
        return 0

    text_terms = set(TOKEN_RE.findall((text or "").lower()))
    matched_terms = [term for term in query_terms if term in text_terms]

    return len(matched_terms) / len(query_terms)


def get_tag_match_score(query_labels, thread_labels):
    query_label_scores = {
        label["id"]: label["score"]
        for label in query_labels
    }
    thread_label_scores = {
        label["id"]: label["score"]
        for label in (thread_labels or [])
    }

    if not query_label_scores or not thread_label_scores:
        return 0

    shared_label_ids = query_label_scores.keys() & thread_label_scores.keys()
    raw_score = sum(
        query_label_scores[label_id] * thread_label_scores[label_id]
        for label_id in shared_label_ids
    )
    return min(raw_score, 1)


def normalize_count(value, max_value):
    if not max_value:
        return 0

    return math.log1p(value) / math.log1p(max_value)


def get_recency_score(thread, now):
    age = now - thread.created_at
    age_days = max(age.total_seconds() / 86400, 0)

    return 0.5 ** (age_days / RECENCY_HALF_LIFE_DAYS)


def add_search_scores(candidate_threads, query_terms, query_labels):
    threads = list(candidate_threads)

    if not threads:
        return []

    max_likes = max(thread.likes for thread in threads)
    max_comments = max(thread.comment_count for thread in threads)
    max_views = max(thread.view_count for thread in threads)
    now = timezone.now()

    for thread in threads:
        title_score = get_text_match_score(query_terms, thread.title)
        description_score = get_text_match_score(query_terms, thread.description)

        thread.title_match_score = title_score
        thread.description_match_score = description_score
        thread.text_match_score = (
            (TITLE_TEXT_WEIGHT * title_score) +
            (DESCRIPTION_TEXT_WEIGHT * description_score)
        )
        thread.tag_match_score = get_tag_match_score(query_labels, thread.topic_labels)

        like_score = normalize_count(thread.likes, max_likes)
        comment_score = normalize_count(thread.comment_count, max_comments)
        view_score = normalize_count(thread.view_count, max_views)

        thread.engagement_score = (
            (LIKE_ENGAGEMENT_WEIGHT * like_score) +
            (COMMENT_ENGAGEMENT_WEIGHT * comment_score) +
            (VIEW_ENGAGEMENT_WEIGHT * view_score)
        )
        thread.recency_score = get_recency_score(thread, now)

        base_relevance = (
            (TEXT_RELEVANCE_WEIGHT * thread.text_match_score) +
            (TAG_RELEVANCE_WEIGHT * thread.tag_match_score)
        )
        agreement_bonus = thread.text_match_score * thread.tag_match_score
        thread.relevance_score = base_relevance * (
            1 + (AGREEMENT_BONUS_WEIGHT * agreement_bonus)
        )

    # Your notes mention a median engagement baseline. A daily stored value is
    # better later, but request-time median is fine while the app is small.
    engagement_baseline = median(thread.engagement_score for thread in threads)

    ranked_threads = []
    for thread in threads:
        passes_gate = (
            thread.relevance_score >= MIN_RELEVANCE_SCORE or
            thread.tag_match_score >= MIN_TAG_MATCH_SCORE or
            (ALLOW_ANY_TEXT_MATCH and thread.text_match_score > 0)
        )

        thread.passes_search_gate = passes_gate

        if not passes_gate:
            continue

        popularity_factor = max(
            MIN_POPULARITY_FACTOR,
            1 + (thread.engagement_score - engagement_baseline),
        )
        thread.final_search_score = (
            (FINAL_RELEVANCE_WEIGHT * thread.relevance_score) +
            (FINAL_RECENCY_WEIGHT * thread.recency_score)
        ) * popularity_factor

        ranked_threads.append(thread)

    return sorted(
        ranked_threads,
        key=lambda thread: thread.final_search_score,
        reverse=True,
    )
