from django.urls import path
from .views import home, boarding, profile, search
from django.contrib.auth import views as auth_views

urlpatterns = [
    path("", home, name="home"),
    path("search/", search, name="search"),
    path("boarding/", boarding, name="boarding"),
    path("profile/", profile, name="profile"),
    path("logout/", auth_views.LogoutView.as_view(next_page="boarding"), name="logout"),
]
