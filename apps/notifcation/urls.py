from django.urls import path

from .views import get_users_notifications

urlpatterns = [
    path("", get_users_notifications, name="notifications"),
]
