"""
routers/livekit.py — LiveKit Transport API
==========================================
Exposes LiveKit transport endpoints.

NOTE: Voice session creation still lives in POST /api/voice/start (Q2).
      This router handles: token re-issue, transport status, and the
      WebSocket channel that pushes session events to the frontend.

Endpoints:
  GET  /api/livekit/token          Re-issue a caller token for an active session
  GET  /api/livekit/status         Active rooms and agent connection status
  WS   /api/livekit/events/{sid}   Session event stream to frontend
"""

import asyncio
import logging
from typing import Dict, Set

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from security import CurrentUser, get_current_user, require_operator
from config import settings

logger = logging.getLogger("routers.livekit")

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────
# WebSocket notification hub
# Frontend connects here to receive session events from the adapter.
# Keyed by session_id (the universal identifier throughout the system).
# ─────────────────────────────────────────────────────────────────────

class _EventHub:
    """
    Maintains active WebSocket connections per session_id.

    The adapter calls push_event() to send events to the browser.
    Multiple browser connections to the same session are supported
    (e.g. operator + supervisor both watching the same session).
    """

    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}

    def register(self, session_id: str, ws: WebSocket) -> None:
        self._connections.setdefault(session_id, set()).add(ws)

    def unregister(self, session_id: str, ws: WebSocket) -> None:
        conns = self._connections.get(session_id, set())
        conns.discard(ws)
        if not conns:
            self._connections.pop(session_id, None)

    async def push_event(
        self, session_id: str, event_type: str, data: dict
    ) -> None:
        """
        Push a JSON event to all browser connections for a session.
        Called by LiveKitAdapter._notify() via the notify_fn callback.
        """
        import datetime
        conns = self._connections.get(session_id, set())
        if not conns:
            # No frontend connected yet — log and continue (non-fatal)
            logger.debug(
                "EventHub: no listeners for session %s (type=%s)", session_id, event_type
            )
            return

        payload_msg = {
            "type": event_type,
            "session_id": session_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "payload": data,
        }
        dead: Set[WebSocket] = set()

        for ws in list(conns):
            try:
                await ws.send_json(payload_msg)
            except Exception:
                dead.add(ws)

        for ws in dead:
            conns.discard(ws)


# Singleton hub — shared across all sessions and the adapter
event_hub = _EventHub()


# ─────────────────────────────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────────────────────────────

class LiveKitTokenResponse(BaseModel):
    session_id: str
    room_name: str
    livekit_token: str
    livekit_url: str


class LiveKitStatusResponse(BaseModel):
    livekit_enabled: bool
    active_rooms: int
    room_sessions: list


# ─────────────────────────────────────────────────────────────────────
# Lazy singletons (created on first use to avoid import-time side effects)
# ─────────────────────────────────────────────────────────────────────

_token_manager = None
_room_manager  = None
_client        = None
_adapter       = None
_conn_manager  = None


def get_token_manager():
    global _token_manager
    if _token_manager is None:
        from livekit_bridge.token_manager import TokenManager
        _token_manager = TokenManager()
    return _token_manager


def get_room_manager():
    global _room_manager
    if _room_manager is None:
        from livekit_bridge.room_manager import RoomManager
        _room_manager = RoomManager()
    return _room_manager


def get_livekit_client():
    global _client
    if _client is None:
        from livekit_bridge.client import LiveKitClient
        _client = LiveKitClient()
    return _client


def get_adapter():
    """
    Return the shared LiveKitAdapter singleton.

    Wired to:
    - session_manager from routers/voice.py (imported lazily — avoids circular import)
    - event_hub.push_event as the notify callback (pushes events to frontend WS)
    """
    global _adapter
    if _adapter is None:
        from livekit_bridge.adapter import LiveKitAdapter
        # Lazy import of voice router session_manager avoids circular import at
        # module load time. By the time this is first called (from voice_start),
        # both modules are fully loaded.
        from routers.voice import session_manager as voice_session_manager
        _adapter = LiveKitAdapter(
            session_manager=voice_session_manager,
            notify_fn=event_hub.push_event,
        )
    return _adapter


def get_connection_manager():
    """Return the shared ConnectionManager singleton."""
    global _conn_manager
    if _conn_manager is None:
        from livekit_bridge.connection_manager import ConnectionManager
        _conn_manager = ConnectionManager(
            room_manager=get_room_manager(),
            token_manager=get_token_manager(),
            adapter=get_adapter(),
        )
    return _conn_manager


# ─────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────

@router.get("/token", response_model=LiveKitTokenResponse)
def livekit_get_token(
    session_id: str = Query(..., description="Voice session ID"),
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Re-issue a caller token for an existing voice session.

    The primary token is issued by POST /api/voice/start (Q2).
    This endpoint handles re-join after a browser refresh or
    connection drop.
    """
    if not settings.LIVEKIT_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="LiveKit is not enabled on this server (LIVEKIT_ENABLED=false).",
        )

    rm = get_room_manager()
    if not rm.is_active(session_id):
        raise HTTPException(
            status_code=404,
            detail=f"No active LiveKit room for session '{session_id}'. "
                   "Session may have expired or not started via LiveKit.",
        )

    tm = get_token_manager()
    token = tm.generate_caller_token(
        session_id=session_id,
        identity=current_user.service_no,
        display_name=current_user.service_no,
    )

    return LiveKitTokenResponse(
        session_id=session_id,
        room_name=session_id,   # room name == session_id
        livekit_token=token,
        livekit_url=settings.LIVEKIT_URL,
    )


@router.get("/status", response_model=LiveKitStatusResponse)
async def livekit_status():
    """
    Return transport-layer health: active rooms and connection statuses.
    Does not expose voice session business state.
    """
    if not settings.LIVEKIT_ENABLED:
        return LiveKitStatusResponse(
            livekit_enabled=False,
            active_rooms=0,
            room_sessions=[],
        )

    rm = get_room_manager()
    active = rm.list_active()

    return LiveKitStatusResponse(
        livekit_enabled=True,
        active_rooms=rm.active_count(),
        room_sessions=[
            {"session_id": sid, "status": rm.get_status(sid)}
            for sid in active
        ],
    )


@router.post("/flush/{session_id}", status_code=200)
async def livekit_flush(
    session_id: str,
    current_user: CurrentUser = Depends(require_operator),
):
    """
    Manually flush the speech buffer for a session.

    Called by the frontend "Stop & Submit" button to immediately trigger
    end-of-speech processing on whatever audio has accumulated in the
    server-side VAD buffer, without waiting for silence detection.
    """
    # ── TRACE LOG 1: Did the HTTP request reach this endpoint? ────────────────
    logger.info(
        "[TRACE-FLUSH-1] POST /api/livekit/flush REACHED: session=%s  user=%s  "
        "livekit_enabled=%s",
        session_id, current_user.service_no, settings.LIVEKIT_ENABLED,
    )

    if not settings.LIVEKIT_ENABLED:
        logger.warning("[TRACE-FLUSH-1] BLOCKED: LIVEKIT_ENABLED=False — returning 503")
        raise HTTPException(status_code=503, detail="LiveKit not enabled.")

    # ── TRACE LOG 2: Which adapter instance do we have? ───────────────────────
    adapter = get_adapter()
    known_sessions = list(adapter._states.keys())
    logger.info(
        "[TRACE-FLUSH-2] Adapter id=%s  known_sessions=%s  "
        "target_session_present=%s",
        id(adapter), known_sessions, session_id in adapter._states,
    )

    try:
        # ── TRACE LOG 3: Calling flush_speech_buffer ──────────────────────────
        logger.info(
            "[TRACE-FLUSH-3] Calling adapter.flush_speech_buffer(session_id=%s)",
            session_id,
        )
        response_wav = await adapter.flush_speech_buffer(session_id)
        had_audio = response_wav is not None

        # ── TRACE LOG 4: What did flush_speech_buffer return? ─────────────────
        logger.info(
            "[TRACE-FLUSH-4] flush_speech_buffer RETURNED: session=%s  "
            "had_audio=%s  wav_size_bytes=%s",
            session_id, had_audio,
            len(response_wav) if response_wav else 0,
        )

        # ── TRACE LOG 5: Will we publish? ─────────────────────────────────────
        if response_wav:
            logger.info(
                "[TRACE-FLUSH-5] WAV received — calling publish_response: session=%s  "
                "wav_bytes=%d",
                session_id, len(response_wav),
            )
            await adapter.publish_response(session_id, response_wav)
            logger.info(
                "[TRACE-FLUSH-5] publish_response DONE: session=%s", session_id
            )
        else:
            logger.info(
                "[TRACE-FLUSH-5] No WAV to publish (pipeline returned None) — "
                "session=%s  This means either: buffer was empty, STT returned silence, "
                "or voice pipeline had no response for current session state.",
                session_id,
            )

        logger.info(
            "[TRACE-FLUSH-6] Flush complete — returning response: session=%s  "
            "status='flushed'  had_audio=%s",
            session_id, had_audio,
        )
        return {"status": "flushed", "had_audio": had_audio}

    except Exception as exc:
        logger.error(
            "[TRACE-FLUSH-ERR] EXCEPTION in flush endpoint: session=%s  "
            "error_type=%s  error=%s",
            session_id, type(exc).__name__, exc, exc_info=True,
        )
        raise HTTPException(status_code=500, detail=f"Flush failed: {exc}")


@router.websocket("/events/{session_id}")
async def livekit_events(session_id: str, websocket: WebSocket):
    """
    WebSocket stream: pushes session events to the frontend.

    The LiveKitAdapter calls event_hub.push_event() to send events here.
    Events include: speech_started, transcribed, state_change, processing,
    timeout, error, silent.

    Note: business-critical session state lives in VoiceSessionManager.
    This channel only carries frontend notification events.
    """
    await websocket.accept()
    event_hub.register(session_id, websocket)

    logger.info("EventHub: frontend connected: session=%s", session_id)

    try:
        import datetime
        await websocket.send_json({
            "type": "connected",
            "session_id": session_id,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "payload": { "detail": "Listening for session events." }
        })
        
        # If the agent is already connected, the frontend might have missed the 'ready' event 
        # (race condition between Agent joining room and frontend establishing WS).
        rm = get_room_manager()
        from livekit_bridge.room_manager import RoomStatus
        if rm.get_status(session_id) == RoomStatus.CONNECTED:
            await websocket.send_json({
                "type": "ready",
                "session_id": session_id,
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "payload": { "detail": "Agent is already connected and listening." }
            })

        # Keep connection alive until client disconnects
        while True:
            # Receive any message from client (keepalive pings, etc.)
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({
                    "type": "ping",
                    "session_id": session_id,
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "payload": {}
                })

    except WebSocketDisconnect:
        logger.info("EventHub: frontend disconnected: session=%s", session_id)
    except Exception as exc:
        logger.warning("EventHub: error: session=%s  %s", session_id, exc)
    finally:
        event_hub.unregister(session_id, websocket)
