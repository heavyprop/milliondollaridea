from django.conf import settings
from django.db import models

from .comments import Comment
from .threads import Thread


class ThreadLike(models.Model):
    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, related_name="thread_likes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="thread_likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "user"], name="unique_thread_like"
            )
        ]

    def __str__(self):
        return f"{self.user} liked {self.thread}"


class ThreadView(models.Model):
    thread = models.ForeignKey(
        Thread, on_delete=models.CASCADE, related_name="thread_views"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="thread_views"
    )
    seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["thread", "user"], name="unique_thread_view"
            )
        ]

    def __str__(self):
        return f"{self.user} viewed {self.thread} for {self.seconds}s"


class CommentLike(models.Model):
    comment = models.ForeignKey(
        Comment, on_delete=models.CASCADE, related_name="comment_likes"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comment_likes"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["comment", "user"], name="unique_comment_like"
            )
        ]

    def __str__(self):
        return f"{self.user} liked comment {self.comment_id}"
