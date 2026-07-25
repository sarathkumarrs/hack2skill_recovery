"""Orchestration entry point for turning a MoodCheckIn into a CompanionResponse.

This is the one function unit tests exercise directly (with ai_engine.assess_checkin
mocked) — see companion/tests/test_services.py — so risk-rule correctness never
depends on a live API call.
"""

from __future__ import annotations

from django.conf import settings

from checkins.models import MoodCheckIn, StreakRecord
from checkins.services import consecutive_bad_days as compute_consecutive_bad_days

from . import ai_engine, risk_rules
from .ai_engine import AIEngineError
from .models import CompanionResponse

MOOD_HISTORY_LOOKBACK = 7

FALLBACK_SUGGESTED_ACTION = "Consider reaching out to your support person."


def _recent_mood_history(checkin: MoodCheckIn) -> list[str]:
    """Oldest-to-newest moods from the check-ins immediately before this one."""
    previous = (
        MoodCheckIn.objects.filter(user=checkin.user, created_at__lt=checkin.created_at)
        .order_by("-created_at")[:MOOD_HISTORY_LOOKBACK]
    )
    return [c.mood for c in reversed(previous)]


def create_companion_response(
    checkin: MoodCheckIn,
    assessment_transcript: str | None = None,
    force_crisis: bool = False,
) -> CompanionResponse:
    """assessment_transcript lets a caller feed a *different* (typically
    fuller) transcript into the AI assessment than what's stored on
    checkin.voice_transcript — used by the live-call flow, which stores only
    a short summary on the checkin but needs the full conversation transcript
    for an accurate risk read. Defaults to checkin.voice_transcript, so the
    normal tap/hold-to-talk callers are unaffected.

    force_crisis lets a caller that already knows a crisis occurred (e.g. the
    live call's real-time keyword monitor) guarantee the safety floor fires,
    independent of what apply_safety_floor's own keyword scan finds in
    whatever transcript ends up being passed."""
    mood_history = _recent_mood_history(checkin)
    transcript_for_assessment = (
        assessment_transcript if assessment_transcript is not None else checkin.voice_transcript
    )

    streak_record = StreakRecord.objects.filter(user=checkin.user).first()
    streak = streak_record.current_streak if streak_record else 0
    bad_days = compute_consecutive_bad_days(checkin.user, checkin.local_date)

    assessment = None
    error_occurred = False
    error_detail = ""
    try:
        assessment = ai_engine.assess_checkin(
            mood=checkin.mood,
            mood_history=mood_history,
            voice_transcript=transcript_for_assessment,
            streak=streak,
        )
    except AIEngineError as exc:
        error_occurred = True
        error_detail = str(exc)

    risk_level, crisis_flag = risk_rules.apply_safety_floor(
        llm_assessment=assessment,
        mood=checkin.mood,
        voice_transcript=transcript_for_assessment,
        consecutive_bad_days=bad_days,
        force_crisis=force_crisis,
    )

    if assessment is not None:
        message = assessment.message
        suggested_action = assessment.suggested_action
        llm_risk_level = assessment.risk_level
        raw_response_json = assessment.model_dump()
    else:
        message = (
            "I'm having trouble reaching your AI companion right now, but your "
            "check-in has been saved. Please be gentle with yourself today."
        )
        suggested_action = FALLBACK_SUGGESTED_ACTION
        llm_risk_level = ""
        raw_response_json = None

    return CompanionResponse.objects.create(
        checkin=checkin,
        message=message,
        llm_risk_level=llm_risk_level,
        risk_level=risk_level,
        crisis_flag=crisis_flag,
        suggested_action=suggested_action,
        model_name=settings.ANTHROPIC_MODEL,
        raw_response_json=raw_response_json,
        error_occurred=error_occurred,
        error_detail=error_detail,
    )
