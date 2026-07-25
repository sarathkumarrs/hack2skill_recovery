from django.db import models

from checkins.models import MoodCheckIn


class CompanionResponse(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    checkin = models.OneToOneField(
        MoodCheckIn, related_name="companion_response", on_delete=models.CASCADE
    )
    message = models.TextField()
    # Raw model output before the deterministic safety floor is applied — kept
    # for audit/tuning so divergence between the LLM and the floor is visible.
    llm_risk_level = models.CharField(max_length=8, choices=RiskLevel.choices, blank=True)
    # Final risk level actually shown to the user, after risk_rules.apply_safety_floor().
    risk_level = models.CharField(max_length=8, choices=RiskLevel.choices)
    crisis_flag = models.BooleanField(default=False)
    suggested_action = models.CharField(max_length=200)
    model_name = models.CharField(max_length=64, default="claude-opus-5")
    raw_response_json = models.JSONField(blank=True, null=True)
    error_occurred = models.BooleanField(default=False)
    error_detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Response to {self.checkin} — risk={self.risk_level}"
