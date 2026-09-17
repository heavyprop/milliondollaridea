from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import auth_page, block_user, profile, unblock_user, view_user

urlpatterns = [
    path("accounts/", auth_page, name="auth"),
    path("users/<str:username>/", view_user, name="view_user"),
    path("profile/", profile, name="profile"),
    path("logout/", LogoutView.as_view(next_page="boarding"), name="logout"),
    path("users/<str:username>/block/", block_user, name="block_user"),
    path("users/<str:username>/unblock/", unblock_user, name="unblock_user"),
]
