"""Public route composition. Feature routes live with their owning apps."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("apps.feed.urls")),
    path("search/", include("apps.search.urls")),
    path("threads/", include("apps.discussions.urls")),
    path("hosting/", include("apps.hosting.urls")),
    path("", include("apps.accounts.urls")),
    path("admin/", admin.site.urls),
]
