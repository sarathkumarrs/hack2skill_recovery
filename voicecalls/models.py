from django.conf import settings
from django.db import models


class VoiceCallSession(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"  # room created, bot not yet joined
        ACTIVE = "active", "Active"  # bot joined, call in progress
        ENDED = "ended", "Ended"  # call over, awaiting the completion webhook
        COMPLETED = "completed", "Completed"  # MoodCheckIn + CompanionResponse created
        FAILED = "failed", "Failed"  # bot never joined / webhook never arrived / errored

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="voice_call_sessions", on_delete=models.CASCADE
    )
    room_name = models.CharField(max_length=128)
    room_url = models.URLField()
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    # Set by the real-time crisis keyword monitor during the call (see
    # voice_bot/processors.py) — deliberately NOT the full transcript, which
    # is never persisted; see companion.ai_engine.summarize_conversation and
    # the checkin's voice_transcript field for what's actually kept.
    crisis_detected_live = models.BooleanField(default=False)
    checkin = models.OneToOneField(
        "checkins.MoodCheckIn",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voice_call_session",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} — {self.status} ({self.room_name})"
