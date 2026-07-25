"""Claude API integration for the AI recovery companion.

Deliberately framework-free (no Django imports beyond settings) so this
module can be unit tested with the Anthropic client mocked, independent of
any view/request/DB machinery. See companion/services.py for the orchestration
layer that calls this, and companion/risk_rules.py for the deterministic
safety floor applied on top of whatever this module returns.
"""

from __future__ import annotations

import anthropic
from django.conf import settings

from .schemas import CompanionAssessment

SYSTEM_PROMPT = """You are an empathetic recovery coach supporting someone in recovery \
from a substance use disorder.

Rules for your response:
- Respond in under 100 words.
- Do not shame.
- Encourage healthy coping.
- Suggest one actionable next step.
- If severe emotional distress is detected, recommend contacting a trusted person.

Tone: warm, supportive, non-judgmental."""


class AIEngineError(Exception):
    """Raised whenever the Claude call fails or returns something unusable.

    Callers (companion/services.py) must catch this and fall back to the
    deterministic safety floor — never let it reach the view layer directly.
    """


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            timeout=8.0,
        )
    return _client


def _build_user_content(mood: str, mood_history: list[str], voice_transcript: str | None,
                         streak: int) -> str:
    lines = [f"Current mood: {mood}"]
    if mood_history:
        lines.append(f"Previous moods (oldest to newest): {', '.join(mood_history)}")
    if voice_transcript:
        lines.append(f'Voice message: "{voice_transcript}"')
    lines.append(f"Current recovery streak: {streak} day(s)")
    return "\n".join(lines)


def assess_checkin(
    mood: str,
    mood_history: list[str],
    voice_transcript: str | None,
    streak: int,
) -> CompanionAssessment:
    """Call Claude to assess a single check-in.

    Raises AIEngineError on any failure — timeout, refusal, malformed
    structured output, or a missing/invalid API key. Never returns a partial
    or best-guess assessment; callers fall back to risk_rules instead.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise AIEngineError("ANTHROPIC_API_KEY is not configured")

    client = _get_client()
    user_content = _build_user_content(mood, mood_history, voice_transcript, streak)

    try:
        response = client.messages.parse(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
            output_format=CompanionAssessment,
            # Deliberately no `thinking`/`output_config.effort` here: those are
            # Opus-5-era params (needed there to counteract its always-on
            # thinking) and `effort` actively errors on Haiku 4.5. Haiku runs
            # without thinking by default, which is exactly the fast, no-tuning
            # behavior this short classification+generation call wants — if
            # ANTHROPIC_MODEL is ever pointed back at an Opus/Sonnet model,
            # revisit this.
        )
    except anthropic.APIConnectionError as exc:
        # Must be caught before APIError — APIConnectionError is a subclass of it.
        raise AIEngineError(f"Claude connection error: {exc}") from exc
    except anthropic.APIError as exc:
        raise AIEngineError(f"Claude API error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 — any other SDK/parsing failure is still a fallback case
        raise AIEngineError(f"Unexpected error calling Claude: {exc}") from exc

    if response.stop_reason == "refusal":
        raise AIEngineError("Claude declined to respond (safety refusal)")

    parsed = response.parsed_output
    if parsed is None:
        raise AIEngineError("Claude response did not match the expected schema")

    return parsed


SUMMARY_SYSTEM_PROMPT = """You summarize a recovery check-in phone call in one \
short, neutral sentence for a personal wellness log. Do not add commentary, \
advice, or judgment — just a factual recap of what was discussed. Do not \
include the person's exact words if they described self-harm or suicidal \
thoughts; refer to it only as "expressed distress" in that case."""


def summarize_conversation(transcript: str) -> str:
    """One short, neutral recap of a live call's full transcript — used only
    to populate MoodCheckIn.voice_transcript for call check-ins, so the full
    transcript itself never needs to be persisted anywhere. Kept as a
    separate call (not a field on CompanionAssessment) so the well-tested
    assess_checkin/CompanionAssessment path used by every other check-in
    type stays completely untouched. Not latency-sensitive — the caller is
    already on a "wrapping up" screen by the time this runs.

    Raises AIEngineError on failure, same contract as assess_checkin.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise AIEngineError("ANTHROPIC_API_KEY is not configured")
    if not transcript.strip():
        return "A voice check-in call with no recorded conversation."

    client = _get_client()

    try:
        response = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=200,
            system=SUMMARY_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": transcript}],
        )
    except anthropic.APIConnectionError as exc:
        raise AIEngineError(f"Claude connection error: {exc}") from exc
    except anthropic.APIError as exc:
        raise AIEngineError(f"Claude API error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise AIEngineError(f"Unexpected error calling Claude: {exc}") from exc

    if response.stop_reason == "refusal":
        raise AIEngineError("Claude declined to summarize (safety refusal)")

    text_blocks = [block.text for block in response.content if block.type == "text"]
    summary = "".join(text_blocks).strip()
    if not summary:
        raise AIEngineError("Claude returned an empty summary")

    return summary
