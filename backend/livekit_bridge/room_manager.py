"""
livekit/room_manager.py — Room-to-Session Mapping
===================================================
Maintains a registry of active LiveKit rooms keyed by session_id.

Responsibility: Transport state tracking only.

This module NEVER stores voice session state (that lives in VoiceSessionManager).
It only tracks:
  - Which session_ids have an active LiveKit room
  - The connection status of each room's agent Task
  - The asyncio.Task handle so it can be cancelled on session end

Design:
  - In-memory dict — rooms are transient, no persistence needed.
  - One asyncio.Task per room (one agent per room, one process total).
  - Thread-safe via asyncio's single-threaded event loop.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Dict, Optional, List

logger = logging.getLogger("livekit.room_manager")


class RoomStatus:
    CONNECTING = "connecting"
    CONNECTED  = "connected"
    RECONNECTING = "reconnecting"
    DISCONNECTED = "disconnected"
    ERROR      = "error"


@dataclass
class RoomEntry:
    """
    Transport-only state for one active LiveKit room.
    Business state lives in VoiceSessionManager — never here.
    """
    session_id: str
    room_name: str       # == session_id (same identifier throughout the system)
    status: str = RoomStatus.CONNECTING
    agent_task: Optional[asyncio.Task] = field(default=None, repr=False)


class RoomManager:
    """
    Registry of active LiveKit rooms.

    Maps session_id → RoomEntry (transport state only).
    One instance shared across all active sessions in the single FastAPI process.
    """

    def __init__(self) -> None:
        self._rooms: Dict[str, RoomEntry] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, session_id: str) -> RoomEntry:
        """
        Register a new room entry for the given session.

        Called by voice_start (in routers/voice.py) immediately after
        VoiceSessionManager.create_session() — session exists before room.

        Parameters
        ----------
        session_id : str
            The voice session identifier. Also used as the room name.
        """
        entry = RoomEntry(
            session_id=session_id,
            room_name=session_id,   # room name == session_id (Decision #10)
            status=RoomStatus.CONNECTING,
        )
        self._rooms[session_id] = entry
        logger.info("Room registered: session=%s", session_id)
        return entry

    def unregister(self, session_id: str) -> None:
        """
        Remove the room entry and cancel the agent task if running.

        Called when the voice session terminates (COMPLETED / ERROR).
        """
        entry = self._rooms.pop(session_id, None)
        if entry is None:
            return
        if entry.agent_task and not entry.agent_task.done():
            entry.agent_task.cancel()
            logger.info("Agent task cancelled: session=%s", session_id)
        logger.info("Room unregistered: session=%s", session_id)

    # ------------------------------------------------------------------
    # State updates
    # ------------------------------------------------------------------

    def set_status(self, session_id: str, status: str) -> None:
        """Update the connection status of a room's agent."""
        entry = self._rooms.get(session_id)
        if entry:
            entry.status = status
            logger.debug("Room status: session=%s  status=%s", session_id, status)

    def set_agent_task(self, session_id: str, task: asyncio.Task) -> None:
        """Store the asyncio.Task running the agent for later cancellation."""
        entry = self._rooms.get(session_id)
        if entry:
            entry.agent_task = task

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get(self, session_id: str) -> Optional[RoomEntry]:
        """Return the RoomEntry for a session, or None."""
        return self._rooms.get(session_id)

    def get_status(self, session_id: str) -> str:
        """Return connection status string for a session."""
        entry = self._rooms.get(session_id)
        return entry.status if entry else RoomStatus.DISCONNECTED

    def is_active(self, session_id: str) -> bool:
        """True if the session has a registered, connected room."""
        entry = self._rooms.get(session_id)
        return entry is not None and entry.status == RoomStatus.CONNECTED

    def list_active(self) -> List[str]:
        """Return session_ids of all currently active rooms."""
        return [
            sid for sid, e in self._rooms.items()
            if e.status in (RoomStatus.CONNECTED, RoomStatus.CONNECTING)
        ]

    def active_count(self) -> int:
        """Number of rooms currently active or connecting."""
        return len(self.list_active())
