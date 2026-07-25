from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("checkins/", include("checkins.urls")),
    path("notifications/", include("notifications.urls")),
    path("caregivers/", include("caregivers.urls")),
    path("", include("core.urls")),
]
