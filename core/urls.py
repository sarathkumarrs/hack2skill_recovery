from django.urls import path

from . import views

urlpatterns = [
    path("", views.placeholder, name="placeholder"),
    path("manifest.json", views.manifest, name="manifest"),
]
