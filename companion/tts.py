"""ElevenLabs text-to-speech for the AI companion's message.

Deliberately mirrors ai_engine.py's shape (framework-light, a single error
type, no Django request/view coupling) so it stays testable and swappable.
Streams from ElevenLabs' /stream endpoint and proxies chunks straight
through — reduces time-to-first-audio versus buffering the whole clip,
which matters given the PRD's <2s response-time target.
"""

from __future__ import annotations

from typing import Iterator

import requests
from django.conf import settings

ELEVENLABS_STREAM_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"


class TTSError(Exception):
    """Raised whenever ElevenLabs fails to return usable audio."""


def synthesize_speech_stream(text: str) -> Iterator[bytes]:
    """Returns an iterator of audio/mpeg chunks. Raises TTSError immediately
    on auth/connection/non-200 failures, before any bytes are produced —
    callers can therefore try/except around calling this without worrying
    about a partially-started stream."""
    if not settings.ELEVENLABS_API_KEY:
        raise TTSError("ELEVENLABS_API_KEY is not configured")

    url = ELEVENLABS_STREAM_URL.format(voice_id=settings.ELEVENLABS_VOICE_ID)

    try:
        response = requests.post(
            url,
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": settings.ELEVENLABS_MODEL_ID,
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=15,
            stream=True,
        )
    except requests.RequestException as exc:
        raise TTSError(f"ElevenLabs connection error: {exc}") from exc

    if response.status_code != 200:
        detail = response.text[:200]
        response.close()
        raise TTSError(f"ElevenLabs returned {response.status_code}: {detail}")

    return response.iter_content(chunk_size=4096)
