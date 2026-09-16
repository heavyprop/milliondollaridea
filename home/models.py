from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

# related name = post means i can - request.user.posts.all()

class Thread(models.Model):
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posts")
    title = models.CharField(max_length=255)
    description = models.TextField()
    
    subject = models.ForeignKey(
        "Subject",
        on_delete=models.SET_NULL,
        related_name="threads",
        # this allows for the db to have no subject
        null=True,
        # this allows for the field to have no entry
        blank=True,
    )
    # each Thread can have a subject (or not) subject = models.ForeignKey( "Subject", on_delete=models.CASCADE, related_name="threads", # allows the database to store this as NULL null=True, # allows the field to be NULL blank=True,)
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.PositiveIntegerField(default=0)
    views = models.PositiveIntegerField(default=0)
    topic_labels = models.JSONField(default=list, null=True)  # Store the top labels as a JSON field

    def __str__(self):
        return self.title

class Subject(models.Model):
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=50, unique=True)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    followers = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title

class SubjectFollow(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="subject_followers")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subject_followers")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["subject", "user"], name="unique_subject_follower")
        ]

    def __str__(self):
        return f"{self.user} is a follower of {self.subject}"

class ThreadLike(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="thread_likes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="thread_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["thread", "user"], name="unique_thread_like")
        ]

    def __str__(self):
        return f"{self.user} liked {self.thread}"


class ThreadView(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="thread_views")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="thread_views")
    seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["thread", "user"], name="unique_thread_view")
        ]

    def __str__(self):
        return f"{self.user} viewed {self.thread} for {self.seconds}s"


class Comment(models.Model):
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="comments")
    parent = models.ForeignKey("self", on_delete=models.CASCADE, related_name="replies", null=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comments")
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    likes = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.body[:50]


class CommentLike(models.Model):
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name="comment_likes")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="comment_likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["comment", "user"], name="unique_comment_like")
        ]

    def __str__(self):
        return f"{self.user} liked comment {self.comment_id}"
