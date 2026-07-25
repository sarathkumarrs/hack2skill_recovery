"""The real Pipecat pipeline for one live call.

Real Deepgram STT -> Claude LLM -> ElevenLabs TTS conversation, with barge-in
(VAD-based interruption) and a max-duration watchdog (Phase 2), plus a
deterministic crisis-keyword safety processor sitting between STT and the LLM
context aggregator (Phase 3, CrisisGuardProcessor below) — the same
independent-of-the-LLM guarantee companion/risk_rules.py already gives the
text check-in flow, just running turn-by-turn instead of on a final
transcript.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from django.conf import settings
from loguru import logger

from companion.risk_rules import contains_crisis_keyword
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    EndFrame,
    Frame,
    InterruptionFrame,
    TranscriptionFrame,
    TTSSpeakFrame,
    TTSTextFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.services.anthropic.llm import AnthropicLLMService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from .prompts import build_opening_line, build_system_prompt

OnCompleteCallback = Callable[[str, bool], Awaitable[None]]


def _patch_deepgram_language_bug() -> None:
    """pipecat-ai 0.0.108's DeepgramSTTService._build_connect_kwargs sends
    the `language` setting via str(s.language). For the default Language
    enum member that produces the literal string "Language.EN" instead of
    "en" — Deepgram rejects that outright (confirmed by reproducing the
    exact 400 directly against both the raw Deepgram API and its SDK), which
    made every STT connection in this pipeline fail and retry forever.
    Patches in a corrected version that uses the enum's real .value. Safe
    to delete once upstream ships a fix — this only touches the one
    known-broken field."""
    from pipecat.services.deepgram.stt import DeepgramSTTService
    from pipecat.transcriptions.language import Language

    if getattr(DeepgramSTTService._build_connect_kwargs, "_rp_patched", False):
        return

    original = DeepgramSTTService._build_connect_kwargs

    def patched(self):
        kwargs = original(self)
        language = kwargs.get("language")
        if isinstance(language, str) and language.startswith("Language."):
            try:
                kwargs["language"] = Language[language.split(".", 1)[1]].value
            except KeyError:
                logger.warning("Could not fix up unexpected language value: {}", language)
        return kwargs

    patched._rp_patched = True
    DeepgramSTTService._build_connect_kwargs = patched


_patch_deepgram_language_bug()


class CrisisGuardProcessor(FrameProcessor):
    """Independent-of-the-LLM crisis check on every transcribed user turn —
    the live-call twin of companion.risk_rules.contains_crisis_keyword's
    role in the text check-in flow. Sits immediately after STT, before the
    LLM context aggregator, so a crisis phrase is caught before the model
    ever gets a chance to compose its own response to it.

    On a match: broadcasts an interruption (stops any bot speech already in
    flight), speaks the scripted crisis response directly, and swallows the
    triggering TranscriptionFrame instead of forwarding it — the LLM never
    sees that turn. The call continues afterward; this only overrides the
    single turn, not the rest of the conversation. `crisis_detected` is
    read once, after the call ends, to set crisis_detected_live on the
    completion webhook (which then forces risk_level="high" via
    companion.risk_rules.apply_safety_floor's force_crisis param — the same
    unconditional override the keyword rule already gives the text flow)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.crisis_detected = False

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and contains_crisis_keyword(frame.text):
            self.crisis_detected = True
            logger.warning("Crisis keyword detected mid-call — delivering scripted response.")
            await self.broadcast_interruption()
            await self.push_frame(
                TTSSpeakFrame(settings.CRISIS_SCRIPTED_RESPONSE, append_to_context=True),
                direction,
            )
            return

        await self.push_frame(frame, direction)


class TranscriptAccumulatorProcessor(FrameProcessor):
    """Collects (role, text) turns for the whole call, in order — a flat
    list is all Django's completion webhook needs. Simpler cousin of
    Pipecat's own (deprecated) TranscriptProcessor: no thought-tracking, no
    event-handler indirection, just accumulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.turns: list[tuple[str, str]] = []
        self._assistant_parts: list[str] = []

    def _flush_assistant(self) -> None:
        if self._assistant_parts:
            text = "".join(self._assistant_parts).strip()
            if text:
                self.turns.append(("assistant", text))
            self._assistant_parts = []

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame):
            if frame.text and frame.text.strip():
                self.turns.append(("user", frame.text.strip()))
        elif isinstance(frame, TTSTextFrame):
            self._assistant_parts.append(frame.text)
        elif isinstance(frame, (BotStoppedSpeakingFrame, InterruptionFrame, EndFrame)):
            self._flush_assistant()

        await self.push_frame(frame, direction)

    def transcript_text(self) -> str:
        self._flush_assistant()
        return "\n".join(f"{role.capitalize()}: {text}" for role, text in self.turns)


async def run_call(room_url: str, bot_token: str, context: dict, on_complete: OnCompleteCallback) -> None:
    """Runs one live call end-to-end, from the bot joining to the call
    ending (by hangup or the max-duration watchdog). Calls on_complete
    exactly once with (transcript, crisis_detected_live) — the latter is
    True if CrisisGuardProcessor caught a crisis keyword at any point
    during the call, regardless of how the rest of the conversation went."""

    transport = DailyTransport(
        room_url,
        bot_token,
        "Recovery Pulse Companion",
        params=DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=16000,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        ),
    )

    # sample_rate is passed explicitly rather than left to be inferred from
    # the pipeline's StartFrame — in this Pipecat version that inference
    # produced sample_rate=0 by the time DeepgramSTTService opens its
    # websocket, which Deepgram rejects outright (confirmed by reproducing
    # the exact failure directly against the Deepgram SDK). Passing it here
    # takes priority over frame-derived values in the service's own start().
    stt = DeepgramSTTService(api_key=settings.DEEPGRAM_API_KEY, sample_rate=16000)
    llm = AnthropicLLMService(
        api_key=settings.ANTHROPIC_API_KEY,
        settings=AnthropicLLMService.Settings(model=settings.ANTHROPIC_MODEL),
    )
    tts = ElevenLabsTTSService(
        api_key=settings.ELEVENLABS_API_KEY,
        settings=ElevenLabsTTSService.Settings(
            voice=settings.ELEVENLABS_VOICE_ID, model=settings.ELEVENLABS_MODEL_ID
        ),
    )

    system_prompt = build_system_prompt(context)
    llm_context = OpenAILLMContext(messages=[{"role": "system", "content": system_prompt}])
    context_aggregator = llm.create_context_aggregator(llm_context)

    crisis_guard = CrisisGuardProcessor()
    transcript_accumulator = TranscriptAccumulatorProcessor()

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            crisis_guard,
            context_aggregator.user(),
            llm,
            transcript_accumulator,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(pipeline, params=PipelineParams(allow_interruptions=True))

    finished = asyncio.Event()

    @transport.event_handler("on_first_participant_joined")
    async def _on_first_participant_joined(transport, participant):
        await task.queue_frame(TTSSpeakFrame(build_opening_line(context), append_to_context=True))

    @transport.event_handler("on_participant_left")
    async def _on_participant_left(transport, participant, reason):
        await task.queue_frame(EndFrame())

    @transport.event_handler("on_error")
    async def _on_error(transport, error):
        logger.error("Daily transport error: {}", error)

    async def _watchdog() -> None:
        warn_at = max(settings.MAX_CALL_DURATION_SECONDS - 30, 0)
        await asyncio.sleep(warn_at)
        if finished.is_set():
            return
        await task.queue_frame(
            TTSSpeakFrame("We're almost at time for today — let's start wrapping up.", append_to_context=True)
        )
        await asyncio.sleep(settings.MAX_CALL_DURATION_SECONDS - warn_at)
        if finished.is_set():
            return
        await task.queue_frame(
            TTSSpeakFrame("That's our time for today. Take care of yourself.", append_to_context=True)
        )
        await task.queue_frame(EndFrame())

    watchdog_task = asyncio.create_task(_watchdog())
    runner = PipelineRunner(handle_sigint=False)

    try:
        await runner.run(task)
    finally:
        finished.set()
        watchdog_task.cancel()
        transcript = transcript_accumulator.transcript_text()
        await on_complete(transcript, crisis_guard.crisis_detected)
