from django.conf import settings
from django.db import models


class Subject(models.Model):
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    followers = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title


class SubjectFollow(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="subject_followers"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subject_followers",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["subject", "user"], name="unique_subject_follower"
            )
        ]

    def __str__(self):
        return f"{self.user} is a follower of {self.subject}"
