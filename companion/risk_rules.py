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


def _keyword_hit(voice_transcript: str | None) -> bool:
    if not voice_transcript:
        return False
    lowered = voice_transcript.lower()
    return any(keyword in lowered for keyword in CRISIS_KEYWORDS)


def _max_risk(*levels: str) -> str:
    return max(levels, key=RISK_ORDER.get)


def apply_safety_floor(
    llm_assessment: CompanionAssessment | None,
    mood: str,
    voice_transcript: str | None,
    consecutive_bad_days: int = 0,
) -> tuple[str, bool]:
    """Returns (final_risk_level, crisis_flag).

    Rule order:
    1. Keyword override — a crisis phrase in the transcript forces "high" and
       crisis_flag=True unconditionally, regardless of the LLM or any other
       rule. This only depends on local string matching, so it fires even if
       the Claude call never completes.
    2. Mood floor — "craving" floors the result at least "medium".
    3. History floor — 2+ consecutive struggling/craving days floors at
       least "medium". (Wired up fully in Phase 3 once streak tracking
       exists; Phase 2 always passes consecutive_bad_days=0.)
    4. LLM-unavailable fallback — if there's no LLM assessment at all, the
       result is at least "medium", never a silent "low".
    5. Otherwise, the final result is the LLM's own risk level raised to at
       least the floor computed above — the floor only ever raises the
       minimum, never lowers what the LLM said.
    """
    if _keyword_hit(voice_transcript):
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
