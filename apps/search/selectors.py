"""Load Go-ranked post IDs while preserving their order and scores."""

from apps.discussions.selectors import threads_with_stats


def hydrate_ranked_posts(matches):
    posts_by_id = threads_with_stats().in_bulk([match["id"] for match in matches])
    posts = []
    for match in matches:
        post = posts_by_id.get(match["id"])
        if post is not None:
            post.final_search_score = match["score"]
            posts.append(post)
    return posts
