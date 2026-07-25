from django.contrib import admin

from .models import CaregiverInvite, CaregiverLink, CaregiverNotification


@admin.register(CaregiverInvite)
class CaregiverInviteAdmin(admin.ModelAdmin):
    list_display = ("patient", "invite_code", "status", "created_at", "expires_at")
    list_filter = ("status",)
    search_fields = ("patient__username", "patient__email", "invite_code")


@admin.register(CaregiverLink)
class CaregiverLinkAdmin(admin.ModelAdmin):
    list_display = ("patient", "caregiver", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("patient__username", "caregiver__username")


@admin.register(CaregiverNotification)
class CaregiverNotificationAdmin(admin.ModelAdmin):
    list_display = ("caregiver_link", "checkin", "channel", "sent_at")
    list_filter = ("channel",)
