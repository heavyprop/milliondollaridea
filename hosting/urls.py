from django.urls import path

from . import api, views

app_name = "hosting"

urlpatterns = [
    path("", views.index, name="index"),
    path("help/", views.help_page, name="help"),
    path("projects/<str:owner>/<slug:slug>/", views.project_detail, name="project_detail"),
    path("projects/<str:owner>/<slug:slug>/files/<int:file_id>/", views.project_detail, name="file_detail"),
    path("cli/", views.cli_access, name="cli_access"),
    path("cli/tokens/<uuid:token_id>/revoke/", views.revoke_token, name="revoke_token"),
    path("api/me/", api.me, name="api_me"),
    path("api/projects/<str:owner>/<slug:slug>/publish/", api.publish, name="api_publish"),
    path("api/projects/<str:owner>/<slug:slug>/download/", api.download, name="api_download"),
]
