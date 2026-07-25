from django.urls import path

from . import views

urlpatterns = [
    path("create/", views.checkin_create, name="checkin_create"),
    path("<int:checkin_id>/response/", views.checkin_response, name="checkin_response"),
]
