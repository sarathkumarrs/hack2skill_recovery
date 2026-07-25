from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone as dj_timezone

from .models import MoodCheckIn


def _local_date_for(user):
    """Today's calendar date in the user's Profile.timezone, falling back to
    UTC if the stored timezone string is missing or invalid."""
    tz_name = getattr(getattr(user, "profile", None), "timezone", "") or "UTC"
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        tz = ZoneInfo("UTC")
    return dj_timezone.now().astimezone(tz).date()


def create_checkin(user, mood: str, input_method: str, voice_transcript: str | None = None) -> MoodCheckIn:
    return MoodCheckIn.objects.create(
        user=user,
        mood=mood,
        input_method=input_method,
        voice_transcript=voice_transcript or None,
        local_date=_local_date_for(user),
    )
