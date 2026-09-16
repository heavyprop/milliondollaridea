from django.conf import settings
from django.db import models


class Thread(models.Model):
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts"
    )
    title = models.CharField(max_length=255)
    description = models.TextField()

    subject = models.ForeignKey(
        "Subject",
        on_delete=models.SET_NULL,
        related_name="threads",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)
    topic_labels = models.JSONField(
        default=list, null=True
    )  # Store the top labels as a JSON field

    def __str__(self):
        return self.title
