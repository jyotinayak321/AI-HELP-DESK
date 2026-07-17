"""
livekit/client.py — LiveKit Admin API Wrapper
===============================================
Thin wrapper around the LiveKit Room Service HTTP API for administrative
operations: creating, querying, and deleting rooms.

Responsibility: LiveKit server admin calls only. No voice logic.

Design:
  - All methods are async (matching FastAPI's async event loop).
  - Used only for setup / teardown — never called on the per-frame audio path.
  - Errors are logged and re-raised so the caller decides recovery strategy.
"""

import logging
from typing import List, Optional

from livekit import api as livekit_api

from config import settings

logger = logging.getLogger("livekit.client")


class LiveKitClient:
    """
    Wrapper around LiveKit RoomServiceClient for administrative room operations.

    One singleton instance is shared across all sessions
    (room creation is infrequent — no need for pooling).
    """

    def __init__(self) -> None:
        self._url = settings.LIVEKIT_URL
        self._api_key = settings.LIVEKIT_API_KEY
        self._api_secret = settings.LIVEKIT_API_SECRET

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ensure_room_exists(self, room_name: str) -> None:
        """
        Create a room if it does not already exist.

        LiveKit creates rooms automatically when the first participant joins,
        but calling this explicitly ensures the room is provisioned before
        the caller tries to connect — avoiding a race condition.

        Parameters
        ----------
        room_name : str
            Room name (= session_id throughout the system).
        """
        try:
            async with livekit_api.LiveKitAPI(
                self._url, self._api_key, self._api_secret
            ) as lk:
                await lk.room.create_room(
                    livekit_api.CreateRoomRequest(name=room_name)
                )
            logger.info("LiveKit room ensured: %s", room_name)
        except Exception as exc:
            logger.error("Failed to create LiveKit room '%s': %s", room_name, exc)
            raise

    async def delete_room(self, room_name: str) -> None:
        """
        Delete a room and disconnect all participants.

        Called when a voice session terminates (COMPLETED or ERROR state).
        LiveKit also auto-expires empty rooms (empty_timeout in config).
        """
        try:
            async with livekit_api.LiveKitAPI(
                self._url, self._api_key, self._api_secret
            ) as lk:
                await lk.room.delete_room(
                    livekit_api.DeleteRoomRequest(room=room_name)
                )
            logger.info("LiveKit room deleted: %s", room_name)
        except Exception as exc:
            # Non-fatal — room may already be gone
            logger.warning("Could not delete LiveKit room '%s': %s", room_name, exc)

    async def list_rooms(self) -> List[str]:
        """
        List all active room names on the LiveKit server.

        Used by the /api/livekit/status endpoint for health monitoring.
        """
        try:
            async with livekit_api.LiveKitAPI(
                self._url, self._api_key, self._api_secret
            ) as lk:
                response = await lk.room.list_rooms(
                    livekit_api.ListRoomsRequest()
                )
                return [r.name for r in response.rooms]
        except Exception as exc:
            logger.error("Failed to list LiveKit rooms: %s", exc)
            return []

    async def list_participants(self, room_name: str) -> List[str]:
        """
        List participant identities in a specific room.

        Used for debugging and health checks.
        """
        try:
            async with livekit_api.LiveKitAPI(
                self._url, self._api_key, self._api_secret
            ) as lk:
                response = await lk.room.list_participants(
                    livekit_api.ListParticipantsRequest(room=room_name)
                )
                return [p.identity for p in response.participants]
        except Exception as exc:
            logger.warning(
                "Could not list participants for room '%s': %s", room_name, exc
            )
            return []
