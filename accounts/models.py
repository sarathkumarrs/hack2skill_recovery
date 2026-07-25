from django.conf import settings
from django.db import models


class Profile(models.Model):
    class SubstanceCategory(models.TextChoices):
        ALCOHOL = "alcohol", "Alcohol addiction"
        DRUGS = "drugs", "Drug addiction"
        NICOTINE = "nicotine", "Nicotine dependence"
        PRESCRIPTION = "prescription_medication", "Prescription medication misuse"
        OTHER = "other", "Other"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    display_name = models.CharField(max_length=100, blank=True)
    recovery_start_date = models.DateField(null=True, blank=True)
    substance_category = models.CharField(
        max_length=32, choices=SubstanceCategory.choices, blank=True
    )
    # IANA timezone name (e.g. "Asia/Kolkata") — drives local_date computation
    # for check-ins/streaks and the daily reminder scheduling in Phase 4.
    timezone = models.CharField(max_length=64, default="UTC")
    high_contrast_mode = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.display_name or self.user.get_username()
