from django.urls import path

from . import views

urlpatterns = [
    path("", views.splash, name="splash"),
    path("home/", views.home, name="home"),
    path("manifest.json", views.manifest, name="manifest"),
]
