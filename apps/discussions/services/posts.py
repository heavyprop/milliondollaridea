"""Post creation, including automatic topic classification."""

from apps.discussions.models import Thread
from apps.recommendations.classification import get_top_labels


def create_post(*, author, title, description, subject=None):
    return Thread.objects.create(
        author=author,
        title=title,
        description=description,
        subject=subject,
        topic_labels=get_top_labels(title, description),
    )
