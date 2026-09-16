from django.urls import path

from .api import account, transfers
from .views import pages, projects, tokens

app_name = "hosting"

urlpatterns = [
    path("", projects.index, name="index"),
    path("help/", pages.help_page, name="help"),
    path(
        "projects/<str:owner>/<slug:slug>/",
        projects.project_detail,
        name="project_detail",
    ),
    path(
        "projects/<str:owner>/<slug:slug>/files/<int:file_id>/",
        projects.project_detail,
        name="file_detail",
    ),
    path("cli/", tokens.cli_access, name="cli_access"),
    path(
        "cli/tokens/<uuid:token_id>/revoke/", tokens.revoke_token, name="revoke_token"
    ),
    path("api/me/", account.me, name="api_me"),
    path(
        "api/projects/<str:owner>/<slug:slug>/publish/",
        transfers.publish,
        name="api_publish",
    ),
    path(
        "api/projects/<str:owner>/<slug:slug>/download/",
        transfers.download,
        name="api_download",
    ),
]
