from django.apps import AppConfig


class DiscussionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.discussions"
    verbose_name = "Discussions"
    # Persistence identity only: keep existing tables, migrations, and permissions.
    label = "home"
