from django.urls import path
from .views import auth_page

urlpatterns = [
    path("", auth_page, name="auth")
]