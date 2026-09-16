"""Discussion models. The legacy database label is documented in apps.py."""

from .comments import Comment
from .interactions import CommentLike, ThreadLike, ThreadView
from .subjects import Subject, SubjectFollow
from .threads import Thread

__all__ = [
    "Subject",
    "SubjectFollow",
    "Thread",
    "Comment",
    "CommentLike",
    "ThreadLike",
    "ThreadView",
]
