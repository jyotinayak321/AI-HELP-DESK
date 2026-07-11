"""
livekit/adapter.py — LiveKit ↔ Voice Layer Adapter
=====================================================
THE integration boundary between LiveKit transport and the existing Voice Layer.

This is the ONLY file in livekit/ that imports from voice/.
It delegates all voice processing to the existing modules immediately —
it contains no VAD logic, no STT logic, no validation logic, no session
state management, and no ticket logic of its own.

Inbound interface (Q4):
    process_live_audio(session_id, pcm_bytes, sample_rate)
    → returns Optional[bytes] (WAV response if AI response generated)

Outbound:
    publish_response(session_id, wav_bytes)
    → streams TTS WAV bytes in-memory to LiveKit AudioSource

Audio format contract:
    Inbound:  raw 16-bit PCM from rtc.AudioFrame.data (any sample rate)
    Adapter:  resamples to 16kHz if needed (VAD requires exactly 16kHz)
    Voice Layer receives: WAV bytes (16-bit, 16kHz, mono) — same as existing path
    Outbound: WAV bytes from TTS engine streamed to rtc.AudioSource

No temp files. All audio in memory via bytearray / io.BytesIO.

Design decisions implemented:
  Q1: Single asyncio.Lock on SpeechToTextEngine. Serializes concurrent calls.
      Field LIVEKIT_STT_POOL_SIZE=1 in config. Upgrade path: replace lock
      with asyncio.Semaphore(pool_size) when pool is introduced.
  Q4: Single adapter interface — process_live_audio() is the only entry point
      for the LiveKit layer. receive_track() drives it from an rtc.AudioStream.
"""

import io
import wave
import asyncio
import logging
import numpy as np
from math import gcd
from dataclasses import dataclass, field
from typing import Dict, Optional, Callable, Awaitable

from livekit import rtc

from config import settings

logger = logging.getLogger("livekit.adapter")

# ── Q1: Shared STT lock — one at a time, upgrade-ready ──────────────────────
# To upgrade to a pool: replace with asyncio.Semaphore(settings.LIVEKIT_STT_POOL_SIZE)
_stt_lock = asyncio.Lock()

# Chunk size for streaming WAV to LiveKit AudioSource (samples per push)
_PLAYBACK_CHUNK_SAMPLES = 1024

# VAD/STT audio target format
_TARGET_SAMPLE_RATE = 16000    # Hz — required by Silero VAD
_TARGET_SAMPLE_WIDTH = 2       # bytes — 16-bit PCM
_TARGET_CHANNELS = 1           # mono


@dataclass
class _SessionAudioState:
    """
    Per-session audio accumulation state.
    Transport state only — no voice session business state here.
    """
    frame_buffer: object                          # voice/audio.py FrameBuffer
    detector: object                              # voice/vad.py StreamingEndpointDetector
    audio_source: rtc.AudioSource                 # LiveKit output track
    speech_buffer: bytearray = field(default_factory=bytearray)
    was_speaking: bool = False
    # Mic gate: when False, ALL inbound audio is silently discarded.
    # Held closed from the moment a confirmation is accepted until
    # publish_response() finishes streaming the TTS, preventing residual
    # confirmation audio from bleeding into the complaint pipeline.
    mic_enabled: bool = True
    # Handle to the adapter-recv-* asyncio.Task driving this session's
    # audio stream. Stored so connection_manager can cancel it BEFORE
    # calling room.disconnect(), preventing capture_frame on a closed source.
    recv_task: Optional[asyncio.Task] = field(default=None, repr=False)
    # Per-session lock: prevents concurrent pipeline runs (manual flush + VAD
    # end_of_speech) from both entering _run_voice_pipeline simultaneously.
    pipeline_lock: object = field(default_factory=asyncio.Lock)


# ── Notify callback type ─────────────────────────────────────────────────────
# async fn(session_id: str, event: str, data: dict) → None
NotifyFn = Callable[[str, str, dict], Awaitable[None]]


class LiveKitAdapter:
    """
    Thin adapter: LiveKit audio transport ↔ existing Voice Layer.

    The only file in livekit/ that imports voice modules.
    All voice processing is delegated immediately to those modules.

    One LiveKitAdapter instance is shared across all rooms
    (per-session state is stored in _states dict, keyed by session_id).
    """

    def __init__(
        self,
        session_manager,    # VoiceSessionManager — the single source of truth
        notify_fn: NotifyFn,
    ) -> None:
        """
        Parameters
        ----------
        session_manager : VoiceSessionManager
            The singleton from routers/voice.py. NOT owned by this adapter.
        notify_fn : async callable
            Sends JSON events to the frontend WebSocket channel for a session.
            Signature: async fn(session_id, event_name, data_dict)
        """
        self._session_manager = session_manager
        self._notify_fn = notify_fn
        self._states: Dict[str, _SessionAudioState] = {}

    # ------------------------------------------------------------------
    # Session lifecycle (called by ConnectionManager)
    # ------------------------------------------------------------------

    def register_session(
        self,
        session_id: str,
        audio_source: rtc.AudioSource,
    ) -> None:
        """
        Set up per-session audio state when the agent joins a room.

        Creates fresh FrameBuffer and StreamingEndpointDetector for this
        session — the same classes used by the existing WebSocket VAD path.

        Called by ConnectionManager._run_connected() before room.connect().
        """
        # Lazy import — keeps livekit/ import-clean even if voice/ is heavy
        from voice.audio import FrameBuffer
        from voice.vad import StreamingEndpointDetector

        self._states[session_id] = _SessionAudioState(
            frame_buffer=FrameBuffer(),
            detector=StreamingEndpointDetector(
                silence_duration_ms=2500,
                speech_threshold=0.4,
                min_speech_ms=300,
            ),
            audio_source=audio_source,
        )
        logger.info("Adapter: session registered: %s", session_id)

    def unregister_session(self, session_id: str) -> None:
        """
        Release per-session audio state when the session ends.

        Called by ConnectionManager.disconnect_agent().
        """
        self._states.pop(session_id, None)
        logger.info("Adapter: session unregistered: %s", session_id)

    # ------------------------------------------------------------------
    # Inbound: caller audio → Voice Layer
    # ------------------------------------------------------------------

    async def receive_track(self, session_id: str, track: rtc.Track) -> None:
        """
        Entry point for incoming caller audio from LiveKit.

        Iterates over rtc.AudioStream frames and calls process_live_audio()
        for each chunk. This runs as an asyncio.Task spawned by
        ConnectionManager._on_track_subscribed().

        Pattern adopted from: Live_Kit_PoC/backend/agent.py process_audio().
        """
        # Import here (lazy) to keep the module-level import footprint small.
        # Needed to detect CONFIRMING_SERVICE_NUMBER→CAPTURING_COMPLAINT transitions
        # so we can gate the mic around publish_response().
        from voice.session import SessionState as _SessionState

        stream = rtc.AudioStream(track)
        logger.info(
            "[TRANSPORT] receive_track START: session=%s  track_sid=%s",
            session_id, getattr(track, 'sid', 'unknown'),
        )

        try:
            async for event in stream:
                frame = event.frame
                
                # Log incoming frame metadata (requested by user)
                raw_bytes = bytes(frame.data)
                logger.debug(
                    "LiveKit Frame: SR=%s, Ch=%s, Samples/Ch=%s, Bytes=%s",
                    frame.sample_rate, frame.num_channels, frame.samples_per_channel, len(raw_bytes)
                )

                # Ensure mono: if stereo, average the channels.
                if frame.num_channels > 1:
                    import numpy as np
                    # Ensure the buffer length is a multiple of 2 (int16 = 2 bytes) * num_channels
                    # Interleaved: [L, R, L, R...]
                    samples = np.frombuffer(raw_bytes, dtype=np.int16)
                    # Reshape to (samples_per_channel, num_channels)
                    samples = samples.reshape(-1, frame.num_channels)
                    # Average across channels and cast back to int16
                    mono_samples = samples.mean(axis=1).astype(np.int16)
                    mono_bytes = mono_samples.tobytes()
                else:
                    mono_bytes = raw_bytes

                # Q4 interface: single entry point for all incoming audio
                #
                # Snapshot session state BEFORE the pipeline runs so we can
                # detect a CONFIRMING_SERVICE_NUMBER → CAPTURING_COMPLAINT
                # transition and gate the mic around publish_response().
                _pre_snap = self._session_manager.get_session(session_id)
                _state_before = _pre_snap.state if _pre_snap else None

                response_wav = await self.process_live_audio(
                    session_id=session_id,
                    pcm_bytes=mono_bytes,
                    sample_rate=frame.sample_rate,
                )
                if response_wav:
                    # ── Mic gate: confirm → complaint transition ──────────────
                    # Read post-pipeline state to determine whether the just-
                    # processed utterance caused a confirmation acceptance.
                    _post_snap = self._session_manager.get_session(session_id)
                    _state_after = _post_snap.state if _post_snap else None
                    _audio_state = self._states.get(session_id)

                    _needs_mic_gate = (
                        _state_before == _SessionState.CONFIRMING_SERVICE_NUMBER
                        and _state_after  == _SessionState.CAPTURING_COMPLAINT
                        and _audio_state is not None
                    )
                    if _needs_mic_gate:
                        # Disable mic BEFORE publish_response starts streaming.
                        _audio_state.mic_enabled = False
                        # Flush speech_buffer, FrameBuffer leftovers, and VAD
                        # internal state to discard any confirmation tail audio
                        # that arrived after the end_of_speech trigger.
                        _reset_state(_audio_state)
                        logger.info(
                            "[MIC GATE] session=%s  mic DISABLED — audio/VAD buffers "
                            "flushed before CAPTURING_COMPLAINT  "
                            "(state: %s → %s)",
                            session_id,
                            _state_before.value if _state_before else "?",
                            _state_after.value  if _state_after  else "?",
                        )

                    await self.publish_response(session_id, response_wav)

                    if _needs_mic_gate:
                        # Re-enable only AFTER the full TTS has been streamed.
                        _audio_state.mic_enabled = True
                        logger.info(
                            "[MIC GATE] session=%s  mic RE-ENABLED — "
                            "ready for complaint capture",
                            session_id,
                        )

        except asyncio.CancelledError:
            logger.info(
                "[TRANSPORT] receive_track CANCELLED: session=%s  "
                "— task cancelled cleanly (expected during teardown)",
                session_id,
            )
            raise  # propagate so the task is marked cancelled
        except Exception as exc:
            logger.error(
                "[TRANSPORT] receive_track ERROR: session=%s  error=%s",
                session_id, exc, exc_info=True,
            )
        finally:
            logger.info(
                "[TRANSPORT] receive_track END: session=%s  "
                "— audio stream loop exited",
                session_id,
            )

    # ------------------------------------------------------------------ 
    # Internal: store task handle so connection_manager can cancel it
    # before calling room.disconnect().
    # ------------------------------------------------------------------
    def _set_recv_task(self, session_id: str, task: asyncio.Task) -> None:
        """Record the adapter-recv-* task for safe teardown ordering."""
        state = self._states.get(session_id)
        if state is not None:
            state.recv_task = task

    async def cancel_recv_task(self, session_id: str) -> None:
        """
        Cancel and await the audio-receive task for a session.

        MUST be called by ConnectionManager BEFORE room.disconnect().
        This ensures no capture_frame() calls are in flight when the
        AudioSource is torn down, preventing RtcError: InvalidState.
        """
        state = self._states.get(session_id)
        if state is None or state.recv_task is None:
            return
        task = state.recv_task
        if task.done():
            logger.debug(
                "[TRANSPORT] session=%s  recv_task already done — skip cancel",
                session_id,
            )
            return
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        logger.info(
            "[TRANSPORT] session=%s  recv_task cancelled before room.disconnect()",
            session_id,
        )

    async def process_live_audio(
        self,
        session_id: str,
        pcm_bytes: bytes,
        sample_rate: int = 48000,
    ) -> Optional[bytes]:
        """
        PRIMARY ADAPTER INTERFACE (Q4).

        Called for every audio chunk arriving from LiveKit.
        Delegates entirely to existing voice modules — no business logic here.

        Parameters
        ----------
        session_id : str
            Voice session identifier. Same ID used by VoiceSessionManager.
        pcm_bytes : bytes
            Raw 16-bit PCM from rtc.AudioFrame.data.
        sample_rate : int
            Sample rate of the incoming frame (typically 48000 from browser).

        Returns
        -------
        Optional[bytes]
            WAV bytes of TTS response when end-of-speech triggers a complete
            pipeline run. None while still accumulating audio.
        """
        state = self._states.get(session_id)
        if state is None:
            return None

        # ── Mic gate: discard all inbound audio while TTS is streaming ────
        # Prevents confirmation tail audio (e.g. trailing "Yes") from
        # accumulating in speech_buffer and firing a spurious pipeline run
        # immediately after the CONFIRMING → CAPTURING_COMPLAINT transition.
        if not state.mic_enabled:
            logger.debug(
                "[MIC GATE] session=%s  mic gated — discarding %d PCM bytes",
                session_id, len(pcm_bytes),
            )
            return None

        # ── Step 1: Resample to 16kHz (VAD requirement) ──────────────────
        pcm_16k = _resample_to_16khz(pcm_bytes, sample_rate)

        logger.debug(
            "VAD input check: session=%s, src_bytes=%s -> resampled_bytes=%s",
            session_id, len(pcm_bytes), len(pcm_16k)
        )

        # ── Step 2: Accumulate speech bytes in-memory ─────────────────────
        state.speech_buffer.extend(pcm_16k)

        # ── Step 3: Feed into FrameBuffer → VAD ──────────────────────────
        # Delegates to voice/audio.py (FrameBuffer) and voice/vad.py
        for vad_frame in state.frame_buffer.add_chunk(pcm_16k):
            vad_result = state.detector.process_frame(vad_frame)

            # Notify frontend on first detected speech (once per utterance)
            if state.detector._has_spoken and not state.was_speaking:
                state.was_speaking = True
                await self._notify(session_id, "speech_started", {})

            if vad_result == "end_of_speech":
                # ── Build in-memory WAV from accumulated PCM ──────────────
                # Acquire the per-session lock so a concurrent manual flush
                # (Stop & Submit button) cannot also enter the pipeline.
                if state.pipeline_lock.locked():
                    logger.info(
                        "[VAD] session=%s  end_of_speech while pipeline already running "
                        "(flush in progress?) — skipping this utterance",
                        session_id,
                    )
                    _reset_state(state)
                    return None
                async with state.pipeline_lock:
                    wav_bytes = _build_wav(state.speech_buffer)
                    _reset_state(state)
                    # ── TRACE LOG (VAD PATH): calling the shared pipeline ──────────
                    logger.info(
                        "[TRACE-VAD-PIPELINE] end_of_speech triggered: session=%s  "
                        "wav_bytes=%d  "
                        "Calling _run_voice_pipeline() — SAME function as flush path.",
                        session_id, len(wav_bytes),
                    )
                    # ── Delegate entire voice pipeline to existing modules ─────
                    return await self._run_voice_pipeline(session_id, wav_bytes)

            elif vad_result == "timeout":
                _reset_state(state)
                await self._notify(
                    session_id, "timeout",
                    {"detail": "No speech detected within the time limit."},
                )

        return None

    # ------------------------------------------------------------------
    # Outbound: TTS audio → LiveKit
    # ------------------------------------------------------------------

    async def publish_response(self, session_id: str, wav_bytes: bytes) -> None:
        """
        Stream TTS WAV bytes in-memory to the LiveKit AudioSource.

        No temp files. Reads WAV header for format, streams PCM frames.
        Pattern adopted from: Live_Kit_PoC/backend/play_wav.py (adapted to
        accept bytes instead of a file path).
        """
        state = self._states.get(session_id)
        if state is None:
            logger.warning(
                "[TRANSPORT] publish_response: no state for session=%s — "
                "audio_source may have already been released",
                session_id,
            )
            return

        if not wav_bytes:
            return

        try:
            buf = io.BytesIO(wav_bytes)
            with wave.open(buf, "rb") as wav:
                sample_rate  = wav.getframerate()
                num_channels = wav.getnchannels()
                sample_width = wav.getsampwidth()
                total_frames = wav.getnframes()
                duration_s   = total_frames / sample_rate if sample_rate else 0

                logger.info(
                    "[TRANSPORT] publish_response START: session=%s  "
                    "rate=%d  ch=%d  bytes=%d  duration=%.2fs",
                    session_id, sample_rate, num_channels,
                    len(wav_bytes), duration_s,
                )

                frame_idx = 0
                _LOG_EVERY_N = 20   # log a progress line every 20 chunks

                while True:
                    pcm = wav.readframes(_PLAYBACK_CHUNK_SAMPLES)
                    if not pcm:
                        break

                    samples_per_channel = len(pcm) // (num_channels * sample_width)
                    frame_idx += 1

                    if frame_idx % _LOG_EVERY_N == 0:
                        logger.debug(
                            "[TRANSPORT] publish_response PROGRESS: session=%s  "
                            "chunk=%d  samples_per_ch=%d",
                            session_id, frame_idx, samples_per_channel,
                        )

                    audio_frame = rtc.AudioFrame(
                        data=pcm,
                        sample_rate=sample_rate,
                        num_channels=num_channels,
                        samples_per_channel=samples_per_channel,
                    )
                    try:
                        await state.audio_source.capture_frame(audio_frame)
                    except Exception as frame_exc:
                        exc_name = type(frame_exc).__name__
                        exc_str  = str(frame_exc)
                        if "InvalidState" in exc_str or "InvalidState" in exc_name:
                            logger.error(
                                "[TRANSPORT] publish_response INVALID_STATE: session=%s  "
                                "chunk=%d/%d  — audio_source closed before TTS finished.  "
                                "This usually means room.disconnect() raced with playback. "
                                "error=%s",
                                session_id, frame_idx,
                                total_frames // _PLAYBACK_CHUNK_SAMPLES + 1,
                                exc_str,
                            )
                        else:
                            logger.error(
                                "[TRANSPORT] publish_response capture_frame error: "
                                "session=%s  chunk=%d  error=%s",
                                session_id, frame_idx, exc_str, exc_info=True,
                            )
                        # Stop playback — source is gone
                        return

                    # Pace the stream to real-time (prevents buffer overflow)
                    await asyncio.sleep(samples_per_channel / sample_rate)

                logger.info(
                    "[TRANSPORT] publish_response DONE: session=%s  "
                    "total_chunks=%d  duration=%.2fs",
                    session_id, frame_idx, duration_s,
                )

        except Exception as exc:
            logger.error(
                "[TRANSPORT] publish_response FAILED (outer): session=%s  error=%s",
                session_id, exc, exc_info=True,
            )

    # ------------------------------------------------------------------
    # Private: Voice Layer delegation
    # ------------------------------------------------------------------

    async def _run_voice_pipeline(
        self, session_id: str, wav_bytes: bytes
    ) -> Optional[bytes]:
        """
        Delegate to the existing Voice Layer.

        Reads session state from VoiceSessionManager (the single source of
        truth). Routes to the correct existing handler. Returns TTS WAV bytes
        if a spoken response should be sent to the caller.

        This method has read access to session state for routing only —
        it never writes session state directly. All state transitions happen
        inside the existing voice modules that are called from here.
        """
        from voice.session import SessionState
        from voice.stt import SpeechToTextEngine
        from voice.tts import TextToSpeechEngine

        # ── TRACE LOG: SINGLE SHARED PIPELINE ENTRY ──────────────────────────────
        # Both VAD end_of_speech and manual Stop & Submit converge here.
        # Check your call stack: caller is either process_live_audio() (VAD path)
        # or flush_speech_buffer() (manual path). Both are identical from this point.
        import traceback
        caller_frame = traceback.extract_stack()[-2]
        logger.info(
            "[TRACE-PIPELINE-ENTRY] _run_voice_pipeline CALLED: session=%s  "
            "wav_bytes=%d  caller_function='%s' (line %d in %s)  "
            "This is the ONE shared pipeline — both VAD and flush converge here.",
            session_id, len(wav_bytes),
            caller_frame.name, caller_frame.lineno, caller_frame.filename.split('\\')[-1],
        )

        session = self._session_manager.get_session(session_id)
        if session is None:
            logger.warning(
                "[TRACE-PIPELINE-ENTRY] session=%s NOT FOUND in VoiceSessionManager — "
                "returning None. The session may have been ended or never created.",
                session_id,
            )
            return None

        logger.info(
            "[TRACE-PIPELINE-ENTRY] session=%s  current_state=%s  service_no=%s",
            session_id,
            session.state.value if hasattr(session.state, 'value') else session.state,
            getattr(session, 'service_no', 'N/A'),
        )

        # ── STT ── (Q1: single lock, CPU-bound in executor)
        await self._notify(session_id, "processing", {"stage": "stt"})
        loop = asyncio.get_event_loop()

        logger.info(
            "[TRACE-STT] Acquiring STT lock and running transcription: session=%s  "
            "wav_bytes=%d",
            session_id, len(wav_bytes),
        )
        async with _stt_lock:
            stt = SpeechToTextEngine(
                model_size=settings.STT_MODEL_SIZE,
                device=settings.STT_DEVICE,
                compute_type=settings.STT_COMPUTE_TYPE,
            )
            stt_result = await loop.run_in_executor(
                None, lambda: stt.transcribe(wav_bytes)
            )

        logger.info(
            "[TRACE-STT] STT result: session=%s  text=%r  is_silent=%s  "
            "confidence=%.3f  language=%s",
            session_id,
            (stt_result.text or '')[:120],
            stt_result.is_silent,
            stt_result.confidence,
            stt_result.language,
        )

        if stt_result.is_silent or not stt_result.text.strip():
            logger.info(
                "[TRACE-STT] STT result is SILENT or empty — session=%s  "
                "is_silent=%s  text=%r  "
                "Returning None (pipeline ends here, no state change, no TTS).",
                session_id, stt_result.is_silent, stt_result.text,
            )
            await self._notify(session_id, "silent", {})
            return None

        await self._notify(session_id, "transcribed", {
            "text": stt_result.text,
            "confidence": round(stt_result.confidence, 3),
            "language": stt_result.language,
        })

        # ── Route by current session state (read-only routing) ──
        logger.info(
            "[TRACE-ROUTE] Calling _route_by_state: session=%s  state=%s",
            session_id,
            session.state.value if hasattr(session.state, 'value') else session.state,
        )
        response_text = await self._route_by_state(session_id, session, stt_result)
        logger.info(
            "[TRACE-ROUTE] _route_by_state returned: session=%s  "
            "response_text_is_none=%s  response_text_preview=%r",
            session_id, response_text is None,
            (response_text or '')[:80],
        )
        if not response_text:
            return None

        # ── TTS ── (CPU-bound — run in executor to avoid blocking event loop)
        await self._notify(session_id, "processing", {"stage": "tts"})
        logger.info(
            "[TRACE-TTS] Synthesising TTS: session=%s  text_preview=%r",
            session_id, response_text[:80],
        )
        tts = TextToSpeechEngine()
        wav_response = await loop.run_in_executor(
            None, lambda: tts.synthesise(response_text)
        )
        logger.info(
            "[TRACE-TTS] TTS result: session=%s  wav_size=%s bytes",
            session_id, len(wav_response) if wav_response else 0,
        )

        return wav_response if wav_response else None

    async def _route_by_state(
        self, session_id: str, session, stt_result
    ) -> Optional[str]:
        """
        Route the STT result to the correct existing voice handler.

        Returns the text to be spoken as the AI response, or None.

        This method reads session.state for routing only. All state
        transitions are performed inside the existing handler functions
        using the existing VoiceSessionManager API.
        """
        from voice.session import SessionState

        state = session.state
        transcript_preview = (stt_result.text or "")[:120]

        # ── Structured state-routing log ─────────────────────────────────
        # Every utterance that reaches the pipeline is logged here with its
        # current session state and transcript so we can verify that
        # confirmation speech is never routed into complaint capture.
        logger.info(
            "[VOICE ROUTE] session=%s  state=%s  transcript=%r",
            session_id, state.value, transcript_preview,
        )

        if state == SessionState.CAPTURING_SERVICE_NUMBER:
            return await self._handle_service_number(session_id, stt_result)

        elif state == SessionState.CONFIRMING_SERVICE_NUMBER:
            return await self._handle_confirmation(session_id, stt_result)

        elif state == SessionState.CAPTURING_COMPLAINT:
            return await self._handle_complaint(session_id, session, stt_result)

        else:
            logger.info(
                "[VOICE ROUTE] session=%s  state=%s — no audio handler, "
                "state may require operator action via REST",
                session_id, state.value,
            )
            return None

    async def _handle_service_number(
        self, session_id: str, stt_result
    ) -> Optional[str]:
        """
        Delegate to existing validate_service_number (voice/validators.py).
        Delegate state transition to VoiceSessionManager (voice/session.py).
        Delegate prompt text to voice/prompts.py.
        """
        from voice.session import SessionState, MAX_SERVICE_NUMBER_RETRIES
        from voice.validators import validate_service_number
        from voice.prompts import get_prompt_text, render_dynamic_prompt

        validation = validate_service_number(stt_result.text)

        if validation.is_valid:
            self._session_manager.transition(
                session_id,
                SessionState.CONFIRMING_SERVICE_NUMBER,
                service_no=validation.normalised,
            )
            await self._notify(session_id, "state_change", {
                "state": SessionState.CONFIRMING_SERVICE_NUMBER.value,
                "service_no": validation.normalised,
            })
            # Spell out the service number phonetically for read-back (R-31)
            from voice.tts import TextToSpeechEngine
            spelled = TextToSpeechEngine.normalise_for_speech(validation.normalised)
            return render_dynamic_prompt(
                "confirm_service_number",
                service_number=spelled,
            )
        else:
            retries = self._session_manager.increment_svc_retries(session_id)
            if self._session_manager.should_fallback(session_id):
                self._session_manager.transition(
                    session_id, SessionState.OPERATOR_FALLBACK
                )
                await self._notify(session_id, "state_change", {
                    "state": SessionState.OPERATOR_FALLBACK.value,
                    "reason": validation.error_reason,
                })
                return get_prompt_text("fallback_operator")
            else:
                await self._notify(session_id, "state_change", {
                    "state": SessionState.CAPTURING_SERVICE_NUMBER.value,
                    "retries": retries,
                    "reason": validation.error_reason,
                })
                return render_dynamic_prompt(
                    "retry_service_number",
                    attempt=retries,
                    max_attempts=MAX_SERVICE_NUMBER_RETRIES,
                )

    async def _handle_confirmation(
        self, session_id: str, stt_result
    ) -> Optional[str]:
        """
        Detect yes/no from the caller to confirm the service number.
        Transitions session state via VoiceSessionManager.
        """
        from voice.session import SessionState
        from voice.prompts import get_prompt_text

        text = stt_result.text.lower().strip()
        confirmed = any(w in text for w in ["yes", "correct", "right", "haan", "ha"])
        rejected  = any(w in text for w in ["no", "wrong", "nahi", "nope", "incorrect"])

        if confirmed:
            logger.info(
                "[STATE TRANSITION] session=%s  "
                "CONFIRMING_SERVICE_NUMBER → CAPTURING_COMPLAINT  "
                "transcript=%r",
                session_id, stt_result.text[:120],
            )
            self._session_manager.transition(
                session_id, SessionState.CAPTURING_COMPLAINT
            )
            await self._notify(session_id, "state_change", {
                "state": SessionState.CAPTURING_COMPLAINT.value,
            })
            return get_prompt_text("ask_complaint")

        elif rejected:
            logger.info(
                "[STATE TRANSITION] session=%s  "
                "CONFIRMING_SERVICE_NUMBER → CAPTURING_SERVICE_NUMBER  "
                "transcript=%r",
                session_id, stt_result.text[:120],
            )
            self._session_manager.transition(
                session_id, SessionState.CAPTURING_SERVICE_NUMBER
            )
            await self._notify(session_id, "state_change", {
                "state": SessionState.CAPTURING_SERVICE_NUMBER.value,
            })
            return get_prompt_text("ask_service_number")

        else:
            logger.info(
                "[STATE TRANSITION] session=%s  "
                "CONFIRMING_SERVICE_NUMBER → (re-prompt, unclear)  "
                "transcript=%r",
                session_id, stt_result.text[:120],
            )
            # Unclear — ask again
            return get_prompt_text("confirm_yes_no")

    async def _handle_complaint(
        self, session_id: str, session, stt_result
    ) -> Optional[str]:
        """
        Pass the complaint transcript to the existing classification pipeline.

        The embedder, classifier, and search engine are the same singletons
        used by routers/voice.py POST /complaint. A fresh SQLModel DB session
        is created here for the Intake record.

        Returns the classification summary prompt text for TTS.
        """
        from voice.session import SessionState
        from voice.complaint_processor import process_complaint_transcript
        from database import engine
        from sqlmodel import Session as DBSession

        complaint_text = stt_result.text.strip()

        # ── Defensive confirmation-noise filter ───────────────────────────
        # Last-resort guard: if the mic gate failed to suppress a trailing
        # confirmation utterance (e.g. "Yes.", "Okay."), reject it here
        # rather than create a junk Intake record.
        if _is_confirmation_noise(complaint_text):
            logger.warning(
                "[COMPLAINT FILTER] session=%s  discarded confirmation noise "
                "in CAPTURING_COMPLAINT state: %r — re-prompting for complaint",
                session_id, complaint_text,
            )
            from voice.prompts import get_prompt_text as _get_prompt
            return _get_prompt("ask_complaint")

        loop = asyncio.get_event_loop()

        await self._notify(session_id, "processing", {
            "stage": "classification",
            "transcript": complaint_text,
        })

        try:
            # ── Execute shared pipeline in executor ──
            def _process():
                with DBSession(engine) as db:
                    return process_complaint_transcript(
                        db_session=db,
                        session_manager=self._session_manager,
                        session_id=session_id,
                        raw_transcript=complaint_text,
                        operator_id=session.service_no or "livekit-agent",
                        complainant_service_no=session.service_no,
                        complainant_name=session.complainant_name,
                        complainant_unit=session.complainant_unit,
                        complainant_rank=session.complainant_rank,
                        stt_confidence=stt_result.confidence,
                        stt_language=stt_result.language,
                    )
            
            result_data = await loop.run_in_executor(None, _process)

            if result_data.status == "rejected":
                return result_data.prompt_text

            # The shared pipeline automatically transitions the session state to OPERATOR_REVIEW.
            # We just need to broadcast the state_change for the LiveKit-specific frontend adapter,
            # though the shared pipeline also does WebSocket broadcasts. We'll do it here to ensure
            # any adapter-specific UI components (like the old LiveKit adapter state) are updated.
            await self._notify(session_id, "state_change", {
                "state": SessionState.OPERATOR_REVIEW.value,
                "transcript": result_data.corrected_transcript,
                "fault_type": result_data.fault_type,
                "severity": result_data.severity,
                "application": result_data.candidates[0].application_name if result_data.candidates else "Unknown",
                "intake_id": result_data.intake_id,
                "candidates": [c.model_dump() for c in result_data.candidates] if result_data.candidates else [],
                "potential_duplicates": result_data.potential_duplicates or [],
                "is_repeat_caller": result_data.is_repeat_caller or False,
            })

            return result_data.prompt_text

        except Exception as exc:
            logger.error(
                "Adapter: complaint classification failed: session=%s  error=%s",
                session_id, exc, exc_info=True,
            )
            await self._notify(session_id, "error", {
                "stage": "classification",
                "detail": str(exc),
            })
            return None

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    async def notify_ready(self, session_id: str) -> None:
        """Called by ConnectionManager when the agent is fully connected to the room."""
        await self._notify(session_id, "ready", {"detail": "Agent is connected and listening."})

    async def _notify(self, session_id: str, event: str, data: dict) -> None:
        """Push a JSON event to the frontend WebSocket channel."""
        try:
            await self._notify_fn(session_id, event, data)
        except Exception as exc:
            logger.debug(
                "Adapter: notify failed: session=%s  event=%s  error=%s",
                session_id, event, exc,
            )

    async def flush_speech_buffer(self, session_id: str) -> Optional[bytes]:
        """
        Manual end-of-speech trigger — called when the user presses "Stop & Submit".

        Flushes whatever PCM has been accumulated in the speech_buffer for this
        session and immediately runs the full voice pipeline on it, as if the
        VAD had detected end_of_speech naturally.

        Returns
        -------
        Optional[bytes]
            WAV bytes from the TTS response if a pipeline result was generated.
            None if the buffer is empty (nothing to flush).
        """
        # ── TRACE LOG A: flush_speech_buffer entered ────────────────────────────
        logger.info(
            "[TRACE-FLUSH-A] flush_speech_buffer ENTERED: session=%s  "
            "known_sessions=%s",
            session_id, list(self._states.keys()),
        )

        state = self._states.get(session_id)

        # ── TRACE LOG B: state lookup result ───────────────────────────────────
        if state is None:
            logger.info(
                "[TRACE-FLUSH-B] STATE NOT FOUND for session=%s — "
                "session not registered in adapter._states. "
                "This means ConnectionManager.register_session() was never called, "
                "or session was already unregistered. Known sessions: %s",
                session_id, list(self._states.keys()),
            )
            return None

        buffer_bytes = len(state.speech_buffer)
        logger.info(
            "[TRACE-FLUSH-B] STATE FOUND for session=%s  "
            "speech_buffer=%d bytes  mic_enabled=%s  pipeline_locked=%s  "
            "was_speaking=%s",
            session_id, buffer_bytes,
            state.mic_enabled, state.pipeline_lock.locked(),
            state.was_speaking,
        )

        # ── TRACE LOG C: buffer empty check ──────────────────────────────────
        if not state.speech_buffer:
            logger.info(
                "[TRACE-FLUSH-C] BUFFER EMPTY for session=%s — "
                "nothing to flush. Possible causes: (1) mic not yet enabled, "
                "(2) audio arrived but VAD already drained the buffer in a "
                "concurrent end_of_speech event, (3) mic gate is blocking audio "
                "(mic_enabled=%s).",
                session_id, state.mic_enabled,
            )
            return None

        # ── TRACE LOG D: lock contention check ──────────────────────────────
        if state.pipeline_lock.locked():
            logger.info(
                "[TRACE-FLUSH-D] PIPELINE LOCK HELD for session=%s — "
                "a concurrent VAD end_of_speech is already running the pipeline. "
                "Flush skipped to prevent double-run.",
                session_id,
            )
            return None

        # ── TRACE LOG E: snapshotting buffer and calling shared pipeline ──────
        async with state.pipeline_lock:
            # Snapshot and reset buffer ATOMICALLY inside the lock.
            # After this point, the receive_track loop will write into a fresh buffer.
            wav_bytes = _build_wav(state.speech_buffer)
            _reset_state(state)
            logger.info(
                "[TRACE-FLUSH-E] BUFFER SNAPSHOTTED — session=%s  "
                "pcm_bytes_in_buffer=%d  wav_bytes_built=%d  "
                "Now calling _run_voice_pipeline() — SAME function as VAD end_of_speech path.",
                session_id, buffer_bytes, len(wav_bytes),
            )
            result = await self._run_voice_pipeline(session_id, wav_bytes)
            logger.info(
                "[TRACE-FLUSH-E] _run_voice_pipeline RETURNED: session=%s  "
                "result_is_none=%s  result_size=%s bytes",
                session_id, result is None,
                len(result) if result else 0,
            )
            return result



# ── Module-level helpers (pure functions, no class state) ────────────────────

# Words that — when they make up the entirety of an utterance — indicate a
# confirmation response rather than a genuine complaint. Used by
# _is_confirmation_noise() as a last-resort filter in _handle_complaint().
_CONFIRMATION_NOISE_WORDS: frozenset = frozenset({
    # Affirmative
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "correct", "right",
    "affirmative", "haan", "ha",
    # Negative
    "no", "nope", "nah", "wrong", "incorrect", "nahi", "nai",
})


def _is_confirmation_noise(text: str) -> bool:
    """
    Return True if *text* consists solely of confirmation/rejection words
    and contains no substantive complaint content.

    This is a last-resort guard against stray confirmation audio that slips
    past the mic gate and reaches the complaint-capture pipeline.

    Examples that return True  : "Yes.", "yes yes", "No.", "Okay."
    Examples that return False : "Yes, my email is not working.",
                                 "No connectivity to the server."
    """
    if not text:
        return False
    # Normalise: lower-case, strip trailing punctuation per word
    words = [
        w.strip(".,!?;:'\"")
        for w in text.lower().split()
    ]
    words = [w for w in words if w]   # remove blanks introduced by punctuation

    # Allow up to 3 tokens — anything longer likely has real complaint content
    if not words or len(words) > 3:
        return False
    return all(w in _CONFIRMATION_NOISE_WORDS for w in words)

def _resample_to_16khz(pcm_bytes: bytes, source_rate: int) -> bytes:
    """
    Resample 16-bit PCM from source_rate to 16kHz.

    Silero VAD requires exactly 16kHz. Browser typically sends 48kHz.
    Uses scipy.signal.resample_poly for high-quality rational resampling.
    Falls back to raw bytes if scipy unavailable.
    """
    if source_rate == _TARGET_SAMPLE_RATE:
        return pcm_bytes
    if not pcm_bytes:
        return pcm_bytes

    try:
        from scipy.signal import resample_poly

        samples = np.frombuffer(pcm_bytes, dtype=np.int16).astype(np.float32)
        g  = gcd(source_rate, _TARGET_SAMPLE_RATE)
        up = _TARGET_SAMPLE_RATE // g
        dn = source_rate // g
        resampled = resample_poly(samples, up, dn)
        return resampled.clip(-32768, 32767).astype(np.int16).tobytes()

    except ImportError:
        logger.warning(
            "scipy not installed — skipping resample (VAD may be inaccurate). "
            "Install scipy for correct 48kHz→16kHz resampling."
        )
        return pcm_bytes
    except Exception as exc:
        logger.warning("Resample failed (%s); passing original bytes", exc)
        return pcm_bytes


def _build_wav(speech_buffer: bytearray) -> bytes:
    """Build an in-memory WAV file from accumulated 16-bit PCM at 16kHz."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(_TARGET_CHANNELS)
        w.setsampwidth(_TARGET_SAMPLE_WIDTH)
        w.setframerate(_TARGET_SAMPLE_RATE)
        w.writeframes(bytes(speech_buffer))
    return buf.getvalue()


def _reset_state(state: _SessionAudioState) -> None:
    """Clear accumulation buffers and reset VAD detector for next utterance."""
    state.speech_buffer.clear()
    state.detector.reset()
    state.frame_buffer.reset()
    state.was_speaking = False
