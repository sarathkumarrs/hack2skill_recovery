from django.contrib import admin

from .models import CompanionResponse


@admin.register(CompanionResponse)
class CompanionResponseAdmin(admin.ModelAdmin):
    list_display = (
        "checkin",
        "risk_level",
        "llm_risk_level",
        "crisis_flag",
        "error_occurred",
        "created_at",
    )
    list_filter = ("risk_level", "crisis_flag", "error_occurred")
    readonly_fields = ("created_at",)
