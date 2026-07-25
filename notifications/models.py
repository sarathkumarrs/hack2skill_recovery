import datetime

from django.conf import settings
from django.db import models


class PushSubscription(models.Model):
    """A browser's Web Push subscription. Used for both patients (daily
    reminder) and caregivers (real-time "Notify Caregiver" alerts, Phase 5)
    — the model doesn't distinguish the two, only the caller does."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="push_subscriptions", on_delete=models.CASCADE
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.CharField(max_length=255)
    auth = models.CharField(max_length=255)
    user_agent = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.endpoint[:40]}…"


class NotificationPreference(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="notification_pref", on_delete=models.CASCADE
    )
    reminder_time = models.TimeField(default=datetime.time(20, 0))
    reminder_enabled = models.BooleanField(default=True)
    # Prevents double-sending if the polling command runs more than once/day.
    last_sent_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.user} — {self.reminder_time}"
