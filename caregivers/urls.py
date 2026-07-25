from django.urls import path

from . import views

urlpatterns = [
    path("invite/", views.invite_create, name="caregiver_invite"),
    path("accept/<str:code>/", views.invite_accept, name="caregiver_invite_accept"),
    path("dashboard/", views.dashboard, name="caregiver_dashboard"),
    path("notify/<int:checkin_id>/", views.notify_caregiver, name="notify_caregiver"),
]
