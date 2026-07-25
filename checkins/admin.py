from django.contrib import admin

from .models import MoodCheckIn


@admin.register(MoodCheckIn)
class MoodCheckInAdmin(admin.ModelAdmin):
    list_display = ("user", "mood", "input_method", "local_date", "created_at")
    list_filter = ("mood", "input_method", "local_date")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("created_at",)
