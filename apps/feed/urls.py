from django.urls import path

from .pages import boarding
from .views import home

urlpatterns = [
    path("", home, name="home"),
    path("boarding/", boarding, name="boarding"),
]
