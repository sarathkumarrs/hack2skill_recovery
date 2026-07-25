"""Standalone service that runs the live-call pipeline for Recovery Pulse.

PHASE 2: runs the real Pipecat pipeline (voice_bot/pipeline.py) — Deepgram
STT, Claude LLM, ElevenLabs TTS, real barge-in. Still no safety processor
(Phase 3) — CrisisGuardProcessor lands between STT and the LLM context
aggregator once this real conversation path is proven solid.

Bootstraps Django settings on startup so this process can import the exact
same safety-critical code the main app uses — companion.risk_rules,
companion.ai_engine.SYSTEM_PROMPT — zero drift, not a duplicated copy.
Runs entirely separate from Django's request/response cycle and NEVER
touches the database directly; all persistent state lives in Django, reached
only via the two HTTP edges here (this service's own /internal/start-bot,
and the outbound POST to Django's completion webhook).
"""

from __future__ import annotations

import asyncio
import hmac
import logging
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "recovery.settings")

import django  # noqa: E402

django.setup()

import requests  # noqa: E402
from django.conf import settings  # noqa: E402
from fastapi import FastAPI, Header, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from voice_bot.pipeline import run_call  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice_bot")

app = FastAPI(title="Recovery Pulse Voice Bot")


class StartBotRequest(BaseModel):
    session_id: int
    room_url: str
    bot_token: str
    context: dict


def _check_secret(secret: str | None) -> None:
    expected = settings.VOICE_SERVICE_SHARED_SECRET
    if not expected or not secret or not hmac.compare_digest(secret, expected):
        raise HTTPException(status_code=403, detail="Invalid or missing shared secret.")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/internal/start-bot")
async def start_bot(
    payload: StartBotRequest, x_voice_service_secret: str | None = Header(default=None)
):
    _check_secret(x_voice_service_secret)
    logger.info("Starting bot for session %s in room %s", payload.session_id, payload.room_url)
    # Fire-and-forget: this endpoint returns immediately — Django doesn't
    # wait synchronously for a call to finish.
    asyncio.create_task(_run_and_report(payload.session_id, payload.room_url, payload.bot_token, payload.context))
    return {"status": "started"}


async def _run_and_report(session_id: int, room_url: str, bot_token: str, context: dict) -> None:
    async def on_complete(transcript: str, crisis_detected_live: bool) -> None:
        await asyncio.to_thread(_post_completion, session_id, transcript, crisis_detected_live)

    try:
        await run_call(room_url, bot_token, context, on_complete)
    except Exception:
        logger.exception("Call pipeline failed for session %s", session_id)
        await asyncio.to_thread(_post_completion, session_id, "", False)


def _post_completion(session_id: int, transcript: str, crisis_detected_live: bool) -> None:
    url = f"{settings.DJANGO_BASE_URL}/voicecalls/webhook/complete/"
    for attempt in range(3):
        try:
            response = requests.post(
                url,
                headers={"X-Voice-Service-Secret": settings.VOICE_SERVICE_SHARED_SECRET},
                json={
                    "session_id": session_id,
                    "transcript": transcript,
                    "crisis_detected_live": crisis_detected_live,
                    "ended_reason": "call_ended",
                },
                timeout=10,
            )
            if response.ok:
                logger.info("Completion webhook succeeded for session %s", session_id)
                return
            logger.warning(
                "Completion webhook returned %s: %s", response.status_code, response.text[:200]
            )
        except requests.RequestException as exc:
            logger.warning("Completion webhook attempt %s failed: %s", attempt + 1, exc)
        time.sleep(1.5 * (attempt + 1))

    logger.error("Completion webhook failed after retries for session %s — check manually.", session_id)
