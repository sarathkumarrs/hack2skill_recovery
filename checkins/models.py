from django.conf import settings
from django.db import models


class MoodCheckIn(models.Model):
    class Mood(models.TextChoices):
        GOOD = "good", "Feeling Good"
        OKAY = "okay", "Okay"
        STRUGGLING = "struggling", "Struggling"
        CRAVING = "craving", "Craving"

    class InputMethod(models.TextChoices):
        TAP = "tap", "Tap"
        VOICE = "voice", "Voice"
        CALL = "call", "Call"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, related_name="mood_checkins", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Calendar date in the user's Profile.timezone at creation time — drives
    # streak counting (Phase 3) and "today's mood" without re-deriving it
    # from created_at + a timezone lookup on every read.
    local_date = models.DateField()
    mood = models.CharField(max_length=16, choices=Mood.choices)
    input_method = models.CharField(max_length=8, choices=InputMethod.choices)
    voice_transcript = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "local_date"])]

    def __str__(self):
        return f"{self.user} — {self.mood} ({self.local_date})"


class StreakRecord(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name="streak", on_delete=models.CASCADE
    )
    current_streak = models.PositiveIntegerField(default=0)
    longest_streak = models.PositiveIntegerField(default=0)
    last_checkin_date = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} — {self.current_streak} day streak"
