from django.contrib import admin

from .models import VoiceCallSession


@admin.register(VoiceCallSession)
class VoiceCallSessionAdmin(admin.ModelAdmin):
    list_display = ("user", "status", "crisis_detected_live", "started_at", "ended_at", "checkin")
    list_filter = ("status", "crisis_detected_live")
    search_fields = ("user__username", "user__email", "room_name")
    readonly_fields = ("created_at",)
