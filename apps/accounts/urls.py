from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import auth_page, profile

urlpatterns = [
    path("accounts/", auth_page, name="auth"),
    path("profile/", profile, name="profile"),
    path("logout/", LogoutView.as_view(next_page="boarding"), name="logout"),
]
