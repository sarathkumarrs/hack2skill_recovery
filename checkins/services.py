from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.utils import timezone as dj_timezone

from .models import MoodCheckIn, StreakRecord

BAD_MOODS = {MoodCheckIn.Mood.STRUGGLING, MoodCheckIn.Mood.CRAVING}


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


def update_streak(user, local_date: datetime.date) -> StreakRecord:
    """First check-in of a calendar day increments the streak; a missed day
    resets it to 1; a repeat check-in the same day is a no-op (unlimited
    check-ins/day are allowed, but the streak only counts once per day)."""
    streak, _ = StreakRecord.objects.get_or_create(user=user)

    if streak.last_checkin_date == local_date:
        return streak  # already counted today

    if streak.last_checkin_date == local_date - datetime.timedelta(days=1):
        streak.current_streak += 1
    else:
        streak.current_streak = 1

    streak.longest_streak = max(streak.longest_streak, streak.current_streak)
    streak.last_checkin_date = local_date
    streak.save(update_fields=["current_streak", "longest_streak", "last_checkin_date", "updated_at"])
    return streak


def consecutive_bad_days(user, upto_date: datetime.date) -> int:
    """How many consecutive calendar days, ending at upto_date and going
    backward, had at least one check-in with mood in {struggling, craving}.
    Used by companion.risk_rules as the history-based safety floor."""
    count = 0
    date = upto_date
    while MoodCheckIn.objects.filter(user=user, local_date=date, mood__in=BAD_MOODS).exists():
        count += 1
        date -= datetime.timedelta(days=1)
    return count
