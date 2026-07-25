from django.urls import path

from . import views

urlpatterns = [
    path("start/", views.start, name="voicecall_start"),
    path("webhook/complete/", views.webhook_complete, name="voicecall_webhook_complete"),
    path("<int:session_id>/status/", views.status, name="voicecall_status"),
]
