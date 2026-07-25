"""Orchestration for starting and completing a live voice call session.

Django owns all persistent state — VoiceCallSession, and eventually the
MoodCheckIn/CompanionResponse a call produces. The standalone voice_bot/
service never touches the database; it only exists at the two HTTP edges
this module calls (starting a bot) and is called by (the completion
webhook, handled in views.py, which calls complete_call below).
"""

from __future__ import annotations

import time
import uuid

import requests
from django.conf import settings
from django.utils import timezone

from checkins.models import MoodCheckIn, StreakRecord
from checkins.services import create_checkin, update_streak
from companion import ai_engine
from companion.ai_engine import AIEngineError
from companion.services import create_companion_response

from .models import VoiceCallSession

DAILY_API_BASE = "https://api.daily.co/v1"


class VoiceCallError(Exception):
    """A call could not be started — room creation or the voice_bot handoff
    failed. Never leave a dangling `pending` session with no bot coming."""


class VoiceCallAlreadyActiveError(VoiceCallError):
    """The user already has a pending/active call — one at a time."""


def _daily_headers() -> dict:
    return {
        "Authorization": f"Bearer {settings.DAILY_API_KEY}",
        "Content-Type": "application/json",
    }


def _create_daily_room() -> tuple[str, str]:
    """Returns (room_name, room_url). One private room per call; `exp` is a
    hard backstop that self-destructs the room even if our own cleanup
    (the bot ending gracefully, or the stale-session sweep) fails."""
    if not settings.DAILY_API_KEY:
        raise VoiceCallError("DAILY_API_KEY is not configured")

    room_name = f"rp-{uuid.uuid4().hex[:12]}"
    exp = int(time.time()) + settings.MAX_CALL_DURATION_SECONDS + 300

    try:
        response = requests.post(
            f"{DAILY_API_BASE}/rooms",
            headers=_daily_headers(),
            json={
                "name": room_name,
                "privacy": "private",
                "properties": {
                    "exp": exp,
                    "enable_recording": False,
                    "eject_at_room_exp": True,
                },
            },
            timeout=10,
        )
    except requests.RequestException as exc:
        raise VoiceCallError(f"Daily room creation failed: {exc}") from exc

    if response.status_code not in (200, 201):
        raise VoiceCallError(f"Daily returned {response.status_code}: {response.text[:200]}")

    data = response.json()
    return data["name"], data["url"]


def _create_daily_token(room_name: str, *, is_owner: bool) -> str:
    exp = int(time.time()) + settings.MAX_CALL_DURATION_SECONDS + 300

    try:
        response = requests.post(
            f"{DAILY_API_BASE}/meeting-tokens",
            headers=_daily_headers(),
            json={"properties": {"room_name": room_name, "exp": exp, "is_owner": is_owner}},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise VoiceCallError(f"Daily token creation failed: {exc}") from exc

    if response.status_code not in (200, 201):
        raise VoiceCallError(f"Daily returned {response.status_code}: {response.text[:200]}")

    return response.json()["token"]


def _call_context(user) -> dict:
    """Light personalization the bot uses to open the call well."""
    streak_record = StreakRecord.objects.filter(user=user).first()
    recent = MoodCheckIn.objects.filter(user=user).order_by("-created_at")[:5]
    return {
        "display_name": user.profile.display_name or user.get_username(),
        "streak": streak_record.current_streak if streak_record else 0,
        "recent_moods": [c.mood for c in reversed(recent)],
    }


def start_call(user) -> tuple[VoiceCallSession, str]:
    """Creates the Daily room, mints tokens, records the session, and hands
    the call off to voice_bot. Returns (session, user_token)."""
    already_active = VoiceCallSession.objects.filter(
        user=user,
        status__in=[VoiceCallSession.Status.PENDING, VoiceCallSession.Status.ACTIVE],
    ).exists()
    if already_active:
        raise VoiceCallAlreadyActiveError("You already have a call in progress.")

    room_name, room_url = _create_daily_room()
    user_token = _create_daily_token(room_name, is_owner=False)
    bot_token = _create_daily_token(room_name, is_owner=True)

    session = VoiceCallSession.objects.create(user=user, room_name=room_name, room_url=room_url)

    try:
        response = requests.post(
            f"{settings.VOICE_SERVICE_URL}/internal/start-bot",
            headers={"X-Voice-Service-Secret": settings.VOICE_SERVICE_SHARED_SECRET},
            json={
                "session_id": session.id,
                "room_url": room_url,
                "bot_token": bot_token,
                "context": _call_context(user),
            },
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        session.status = VoiceCallSession.Status.FAILED
        session.save(update_fields=["status"])
        raise VoiceCallError(f"Couldn't start the voice bot: {exc}") from exc

    session.status = VoiceCallSession.Status.ACTIVE
    session.started_at = timezone.now()
    session.save(update_fields=["status", "started_at"])

    return session, user_token


def complete_call(
    session: VoiceCallSession, transcript: str, crisis_detected_live: bool
) -> MoodCheckIn:
    """Turns a finished call into a real MoodCheckIn + CompanionResponse,
    reusing the exact same checkins/companion functions the tap and
    hold-to-talk flows use — the only difference is a full conversation
    transcript feeds the AI assessment, while only a short summary of it is
    ever persisted (see companion.ai_engine.summarize_conversation)."""
    try:
        summary = ai_engine.summarize_conversation(transcript)
    except AIEngineError:
        # Never let a failed summary block the check-in from being saved —
        # same "never a silent failure, but never block on the non-essential
        # part" spirit as the rest of the safety-floor design.
        summary = "Had a voice check-in call."

    checkin = create_checkin(
        user=session.user,
        mood=MoodCheckIn.Mood.OKAY,
        input_method=MoodCheckIn.InputMethod.CALL,
        voice_transcript=summary,
    )
    update_streak(session.user, checkin.local_date)
    create_companion_response(
        checkin,
        assessment_transcript=transcript,
        force_crisis=crisis_detected_live,
    )

    session.checkin = checkin
    session.crisis_detected_live = crisis_detected_live
    session.status = VoiceCallSession.Status.COMPLETED
    session.ended_at = timezone.now()
    session.save(update_fields=["checkin", "crisis_detected_live", "status", "ended_at"])

    return checkin
