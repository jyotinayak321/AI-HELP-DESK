"""
livekit/connection_manager.py — Agent Room Connection Lifecycle
================================================================
Manages the lifecycle of the AI agent's connection to a LiveKit room.

Responsibility: WebRTC room join/leave, track publishing/subscribing,
reconnect logic, and spawning the adapter for incoming audio.

This module NEVER processes audio, NEVER validates service numbers,
NEVER manages session state. It only:
  1. Connects the agent to the room (token from TokenManager)
  2. Publishes the agent's audio output track
  3. On track_subscribed: hands the track to LiveKitAdapter (the boundary)
  4. On disconnect: attempts reconnect or cleans up

Design:
  - One asyncio.Task per room, all tasks live inside the same FastAPI process.
  - Reconnect: exponential backoff, max 3 attempts, then marks room ERROR.
  - Pattern adopted from: Live_Kit_PoC/backend/agent.py (room.connect,
    publish_track, track_subscribed handler).
"""

import asyncio
import logging
from typing import TYPE_CHECKING, Optional

from livekit import rtc

from config import settings
from livekit_bridge.token_manager import TokenManager
from livekit_bridge.room_manager import RoomManager, RoomStatus

if TYPE_CHECKING:
    from livekit_bridge.adapter import LiveKitAdapter

logger = logging.getLogger("livekit.connection_manager")

# Reconnect parameters
_MAX_RECONNECT_ATTEMPTS = 3
_RECONNECT_BASE_DELAY_S  = 2.0


class ConnectionManager:
    """
    Manages agent connections to LiveKit rooms.

    One ConnectionManager instance is shared across all sessions
    (it spawns one asyncio.Task per room internally).
    """

    def __init__(
        self,
        room_manager: RoomManager,
        token_manager: TokenManager,
        adapter: "LiveKitAdapter",
    ) -> None:
        self._room_manager = room_manager
        self._token_manager = token_manager
        self._adapter = adapter
        self._audio_tasks = set()  # Prevent GC of background tasks

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def connect_agent(self, session_id: str) -> None:
        """
        Spawn an asyncio.Task that runs the agent in the given room.

        Called from routers/voice.py after VoiceSessionManager.create_session()
        and RoomManager.register() — session and room entry exist first.

        The task runs until the session ends or an unrecoverable error occurs.
        """
        task = asyncio.create_task(
            self._agent_loop(session_id),
            name=f"livekit-agent-{session_id[:8]}",
        )
        self._room_manager.set_agent_task(session_id, task)
        logger.info("Agent task spawned: session=%s", session_id)

    async def disconnect_agent(self, session_id: str, reason: str = "unspecified") -> None:
        """
        Stop the agent for a session: cancel task, clean up adapter state.

        Called when the voice session transitions to COMPLETED or ERROR.
        """
        logger.info(
            "[TRANSPORT] disconnect_agent: session=%s  reason=%s",
            session_id, reason,
        )
        self._room_manager.unregister(session_id)
        self._adapter.unregister_session(session_id)
        logger.info("[TRANSPORT] Agent cleaned up: session=%s", session_id)

    # ------------------------------------------------------------------
    # Agent loop (runs as asyncio.Task)
    # ------------------------------------------------------------------

    async def _agent_loop(self, session_id: str) -> None:
        """
        Long-running coroutine: connects agent to room, handles events.

        Implements reconnect with exponential backoff on transient failures.
        """
        attempt = 0
        while attempt <= _MAX_RECONNECT_ATTEMPTS:
            try:
                await self._run_connected(session_id)
                break   # clean exit — session ended normally
            except asyncio.CancelledError:
                logger.info("Agent task cancelled (normal shutdown): session=%s", session_id)
                break
            except Exception as exc:
                attempt += 1
                if attempt > _MAX_RECONNECT_ATTEMPTS:
                    logger.error(
                        "Agent failed after %d attempts: session=%s  error=%s",
                        _MAX_RECONNECT_ATTEMPTS, session_id, exc,
                    )
                    self._room_manager.set_status(session_id, RoomStatus.ERROR)
                    break
                delay = _RECONNECT_BASE_DELAY_S * (2 ** (attempt - 1))
                logger.warning(
                    "Agent connection lost (attempt %d/%d): session=%s  error=%s  retry in %.1fs",
                    attempt, _MAX_RECONNECT_ATTEMPTS, session_id, exc, delay,
                )
                self._room_manager.set_status(session_id, RoomStatus.RECONNECTING)
                await asyncio.sleep(delay)

    async def _run_connected(self, session_id: str) -> None:
        """
        Connect to LiveKit room, publish agent audio track, wait for events.

        Mirrors the structure of Live_Kit_PoC/backend/agent.py main() but:
        - Uses session_id as room name (not hardcoded "demo-room")
        - No temp files (audio source fed by adapter.publish_response)
        - Hands tracks to LiveKitAdapter instead of processing inline
        """
        room = rtc.Room()
        token = self._token_manager.generate_agent_token(session_id)

        # ── Prepare the AI audio output track (agent publishes TTS audio) ──
        audio_source = rtc.AudioSource(
            sample_rate=22050,   # Matches Piper TTS output rate
            num_channels=1,
        )
        audio_track = rtc.LocalAudioTrack.create_audio_track(
            "ai-helpdesk-voice",
            audio_source,
        )

        # ── Register audio_source with adapter before connecting ──
        self._adapter.register_session(session_id, audio_source)

        # ── Event handlers ──
        @room.on("participant_connected")
        def _on_participant_joined(participant):
            logger.info(
                "[TRANSPORT] Participant JOINED: session=%s  identity=%s  sid=%s",
                session_id, participant.identity, participant.sid,
            )

        @room.on("participant_disconnected")
        def _on_participant_left(participant):
            remaining = list(room.remote_participants.values())
            logger.warning(
                "[TRANSPORT] Participant LEFT: session=%s  identity=%s  sid=%s  "
                "remaining_participants=%d %s",
                session_id, participant.identity, participant.sid,
                len(remaining),
                [p.identity for p in remaining],
            )

        @room.on("track_published")
        def _on_track_published(publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            logger.info(
                "[TRANSPORT] Track published: session=%s  participant=%s  kind=%s  sid=%s",
                session_id, participant.identity, publication.kind, publication.sid,
            )

        @room.on("track_subscribed")
        def _on_track_subscribed(track: rtc.Track, publication: rtc.RemoteTrackPublication, participant: rtc.RemoteParticipant):
            """
            Called when the caller's microphone track becomes available.
            Hand it immediately to the adapter — the only integration boundary.
            """
            logger.info(
                "[TRANSPORT] Track SUBSCRIBED: session=%s  participant=%s  "
                "track_sid=%s  kind=%s",
                session_id, participant.identity, track.sid, track.kind,
            )
            if track.kind != rtc.TrackKind.KIND_AUDIO:
                logger.debug(
                    "[TRANSPORT] Ignoring non-audio track from participant=%s",
                    participant.identity,
                )
                return
            if participant.identity == settings.LIVEKIT_AGENT_IDENTITY:
                logger.debug("[TRANSPORT] Ignoring own published audio track")
                return   # don't process our own published track

            logger.info(
                "[TRANSPORT] Starting audio receive loop: session=%s  "
                "participant=%s  track=%s",
                session_id, participant.identity, track.sid,
            )
            # Spawn adapter receive loop — hands audio into existing Voice Layer.
            # Store the task handle back into adapter state so it can be
            # cancelled BEFORE room.disconnect() during teardown.
            task = asyncio.create_task(
                self._adapter.receive_track(session_id, track),
                name=f"adapter-recv-{session_id[:8]}",
            )
            self._adapter._set_recv_task(session_id, task)
            self._audio_tasks.add(task)
            task.add_done_callback(self._audio_tasks.discard)
            task.add_done_callback(
                lambda t: logger.info(
                    "[TRANSPORT] recv_task finished: session=%s  cancelled=%s  "
                    "exception=%s",
                    session_id, t.cancelled(),
                    t.exception() if not t.cancelled() and t.done() and not t.cancelled() else None,
                ) if t.done() else None
            )

        @room.on("reconnecting")
        def _on_reconnecting():
            logger.warning(
                "[TRANSPORT] Room RECONNECTING: session=%s  "
                "— LiveKit WebSocket dropped, attempting reconnect",
                session_id,
            )

        @room.on("reconnected")
        def _on_reconnected():
            logger.info(
                "[TRANSPORT] Room RECONNECTED: session=%s",
                session_id,
            )

        @room.on("disconnected")
        def _on_disconnected(reason=None):
            logger.warning(
                "[TRANSPORT] Room DISCONNECTED: session=%s  reason=%s  "
                "room_state=%s  remote_participants=%d",
                session_id, reason,
                getattr(room, 'connection_state', 'unknown'),
                len(room.remote_participants),
            )

        # ── Connect to room ──
        logger.info(
            "[TRANSPORT] Agent connecting: session=%s  url=%s",
            session_id, settings.LIVEKIT_URL,
        )
        options = rtc.RoomOptions(auto_subscribe=True)
        await room.connect(settings.LIVEKIT_URL, token, options=options)
        self._room_manager.set_status(session_id, RoomStatus.CONNECTED)
        logger.info(
            "[TRANSPORT] Agent CONNECTED: session=%s  room=%s  "
            "agent_identity=%s  agent_sid=%s",
            session_id, room.name,
            room.local_participant.identity,
            room.local_participant.sid,
        )

        # Log remote participants already in the room at connect time
        remote_participants = list(room.remote_participants.values())
        logger.info(
            "[TRANSPORT] Room %s: %d remote participant(s) at connect: %s",
            room.name, len(remote_participants),
            [f"{p.identity} (SID: {p.sid})" for p in remote_participants],
        )

        # ── Publish agent audio output track ──
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE
        await room.local_participant.publish_track(audio_track, options)
        logger.info(
            "[TRANSPORT] Agent audio track published: session=%s",
            session_id,
        )

        # ── Signal frontend that agent is ready ──
        await self._adapter.notify_ready(session_id)

        # ── Wait indefinitely until task is cancelled (session ends) ──
        try:
            await asyncio.Event().wait()
        finally:
            # ── Teardown: correct ordering to prevent RtcError: InvalidState ──
            #
            # Problem: if room.disconnect() fires while publish_response() is in
            # the middle of capture_frame(), the AudioSource becomes invalid and
            # LiveKit raises RtcError: InvalidState on the next frame.
            #
            # Fix: cancel and await the recv task FIRST, which stops any
            # in-flight capture_frame() calls, then disconnect the room.
            logger.info(
                "[TRANSPORT] Teardown BEGIN: session=%s  "
                "— cancelling recv_task before room.disconnect()",
                session_id,
            )
            await self._adapter.cancel_recv_task(session_id)

            logger.info(
                "[TRANSPORT] Teardown: room.disconnect() called: session=%s  "
                "remote_participants=%d",
                session_id, len(room.remote_participants),
            )
            await room.disconnect()
            logger.info(
                "[TRANSPORT] Teardown COMPLETE: session=%s  room disconnected",
                session_id,
            )
