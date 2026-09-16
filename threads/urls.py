from django.urls import path

from .views import create_comment, create_subject, create_thread, like_comment, like_thread, record_thread_view, subject_detail, thread_detail

urlpatterns = [
    path("create/", create_thread, name="create_thread"),
    path("subjects/create/", create_subject, name="create_subject"),
    path("subjects/<int:subject_id>/", subject_detail, name="subject_detail"),
    path("<int:thread_id>/", thread_detail, name="thread_detail"),
    path("<int:thread_id>/comments/create/", create_comment, name="create_comment"),
    path("<int:thread_id>/view/", record_thread_view, name="record_thread_view"),
    path("<int:thread_id>/like/", like_thread, name="like_thread"),
    path("comments/<int:comment_id>/like/", like_comment, name="like_comment"),
]
