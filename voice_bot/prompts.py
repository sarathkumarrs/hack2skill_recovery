"""Live-call system prompt — built on top of, not instead of,
companion.ai_engine.SYSTEM_PROMPT, so the persona/tone/safety framing stays
defined in exactly one place. This module only adds the spoken-conversation
formatting rules a live call needs that a one-shot text response doesn't."""

from __future__ import annotations

from companion.ai_engine import SYSTEM_PROMPT

LIVE_CALL_ADDENDUM = """

You are on a live, real-time voice phone call right now, not writing a \
single text message. A few things that are different about a phone call:
- Keep each turn short — a sentence or two. Long monologues don't work over \
voice; let the conversation breathe and give the person room to respond.
- Do not use any formatting that only makes sense in writing: no markdown, \
no bullet points, no headers, no asterisks.
- Speak naturally, the way a warm, attentive person would on the phone — \
contractions are fine, and it's fine to pause a response with something \
like "mm" or "I hear you" before continuing.
- You don't need to restate the "suggested action" framing from a text \
check-in — just talk through it naturally as part of the conversation.
"""

LIVE_CALL_SYSTEM_PROMPT_TEMPLATE = (
    SYSTEM_PROMPT
    + LIVE_CALL_ADDENDUM
    + """
About the person you're talking to right now:
- Name: {display_name}
- Current recovery streak: {streak} day(s)
- Recent moods (oldest to newest): {recent_moods}
"""
)


def build_system_prompt(context: dict) -> str:
    return LIVE_CALL_SYSTEM_PROMPT_TEMPLATE.format(
        display_name=context.get("display_name") or "there",
        streak=context.get("streak", 0),
        recent_moods=", ".join(context.get("recent_moods") or []) or "no recent check-ins",
    )


def build_opening_line(context: dict) -> str:
    display_name = context.get("display_name") or "there"
    return f"Hi {display_name}, it's your Recovery Pulse check-in. How are you doing today?"
