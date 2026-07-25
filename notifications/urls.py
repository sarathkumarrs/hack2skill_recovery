from django.urls import path

from . import views

urlpatterns = [
    path("subscribe/", views.subscribe, name="push_subscribe"),
    path("preferences/", views.preferences, name="notification_preferences"),
]
