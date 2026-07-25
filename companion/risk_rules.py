"""Deterministic safety floor around the LLM's risk assessment.

The final risk_level shown to the user must never depend solely on Claude's
judgment — this module guarantees a safe minimum even when the model call
fails, times out, or simply disagrees. See the plan's "Safety / Crisis
Handling" section for the full rationale.

IMPORTANT: CRISIS_KEYWORDS below is a starting point, not a clinically
reviewed list. Review and refine it (ideally with input from someone with
clinical/crisis-response experience) before real users rely on it.
"""

from __future__ import annotations

from .schemas import CompanionAssessment

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

CRISIS_KEYWORDS = [
    "can't handle",
    "cant handle",
    "want to die",
    "end it",
    "end my life",
    "hurt myself",
    "kill myself",
    "no point",
    "give up",
    "not worth it",
]


def contains_crisis_keyword(text: str | None) -> bool:
    """Public entry point so other callers (e.g. the live-call safety
    processor in voice_bot/) can reuse this exact check rather than
    reimplementing it — the whole point of the safety floor is that there's
    one place this logic lives."""
    if not text:
        return False
    lowered = text.lower()
    return any(keyword in lowered for keyword in CRISIS_KEYWORDS)


def _max_risk(*levels: str) -> str:
    return max(levels, key=RISK_ORDER.get)


def apply_safety_floor(
    llm_assessment: CompanionAssessment | None,
    mood: str,
    voice_transcript: str | None,
    consecutive_bad_days: int = 0,
    force_crisis: bool = False,
) -> tuple[str, bool]:
    """Returns (final_risk_level, crisis_flag).

    Rule order:
    0. force_crisis — an unconditional override, same shape as the keyword
       rule but triggered by a caller that already knows a crisis occurred
       (e.g. the live-call pipeline's real-time keyword monitor, which sees
       the conversation as it happens rather than a transcript after the
       fact). Checked first so it can never be "out-voted" by anything else.
    1. Keyword override — a crisis phrase in the transcript forces "high" and
       crisis_flag=True unconditionally, regardless of the LLM or any other
       rule. This only depends on local string matching, so it fires even if
       the Claude call never completes.
    2. Mood floor — "craving" floors the result at least "medium".
    3. History floor — 2+ consecutive struggling/craving days floors at
       least "medium".
    4. LLM-unavailable fallback — if there's no LLM assessment at all, the
       result is at least "medium", never a silent "low".
    5. Otherwise, the final result is the LLM's own risk level raised to at
       least the floor computed above — the floor only ever raises the
       minimum, never lowers what the LLM said.
    """
    if force_crisis or contains_crisis_keyword(voice_transcript):
        return "high", True

    floor = "low"
    if mood == "craving":
        floor = _max_risk(floor, "medium")
    if consecutive_bad_days >= 2:
        floor = _max_risk(floor, "medium")

    if llm_assessment is None:
        return _max_risk(floor, "medium"), False

    final = _max_risk(llm_assessment.risk_level, floor)
    return final, False
