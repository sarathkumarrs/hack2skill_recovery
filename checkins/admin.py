from django.contrib import admin

from .models import MoodCheckIn, StreakRecord


@admin.register(MoodCheckIn)
class MoodCheckInAdmin(admin.ModelAdmin):
    list_display = ("user", "mood", "input_method", "local_date", "created_at")
    list_filter = ("mood", "input_method", "local_date")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at",)


@admin.register(StreakRecord)
class StreakRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "current_streak", "longest_streak", "last_checkin_date")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("updated_at",)
