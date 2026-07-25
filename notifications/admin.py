from django.contrib import admin

from .models import NotificationPreference, PushSubscription


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ("user", "user_agent", "created_at")
    search_fields = ("user__username", "user__email", "endpoint")
    readonly_fields = ("created_at",)


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "reminder_time", "reminder_enabled", "last_sent_date")
    search_fields = ("user__username", "user__email")
