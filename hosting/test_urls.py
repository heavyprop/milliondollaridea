from django.http import HttpResponse
from django.urls import include, path


def placeholder(request):
    return HttpResponse()


urlpatterns = [
    path("hosting/", include("hosting.urls")),
    path("", placeholder, name="home"),
    path("profile/", placeholder, name="profile"),
    path("search/", placeholder, name="search"),
]
