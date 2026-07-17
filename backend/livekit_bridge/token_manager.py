"""
livekit/token_manager.py — LiveKit JWT Token Generation
=========================================================
Generates short-lived JWTs that authorize a participant (caller or AI agent)
to join a specific LiveKit room.

Responsibility: Token generation only. No knowledge of session state,
voice processing, or business logic.

Design:
  - Room name == session_id everywhere (single identifier throughout the system).
  - Caller token:  can_publish=True (mic), can_subscribe=True (hears AI).
  - Agent token:   can_publish=True (TTS audio), can_subscribe=True (hears caller).
  - Tokens expire after LIVEKIT_TOKEN_TTL_SECONDS to limit exposure.
  - Stateless — no storage, safe to instantiate multiple times.

Pattern adopted from: Live_Kit_PoC/backend/app.py (AccessToken + VideoGrants).
"""

import logging
from typing import Optional

from livekit.api import AccessToken, VideoGrants

from config import settings

logger = logging.getLogger("livekit.token_manager")

# Token lifetime in seconds. Long enough for a full session (30 min).
LIVEKIT_TOKEN_TTL_SECONDS = 1800


class TokenManager:
    """
    Generates LiveKit JWTs for callers and the AI agent.

    Room name == session_id throughout the system (Architectural Decision #10).
    """

    def __init__(self) -> None:
        self._api_key = settings.LIVEKIT_API_KEY
        self._api_secret = settings.LIVEKIT_API_SECRET

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_caller_token(
        self,
        session_id: str,
        identity: str,
        display_name: Optional[str] = None,
    ) -> str:
        """
        Generate a JWT for the human caller joining the room.

        Parameters
        ----------
        session_id : str
            Used as both the room name and the primary identifier.
        identity : str
            Unique participant identity (e.g. operator service number).
        display_name : str, optional
            Human-readable display name shown in room participant list.

        Returns
        -------
        str
            Signed JWT string the browser passes to room.connect().
        """
        token = (
            AccessToken(self._api_key, self._api_secret)
            .with_identity(identity)
            .with_name(display_name or identity)
            .with_grants(
                VideoGrants(
                    room_join=True,
                    room=session_id,        # room name == session_id
                    can_publish=True,       # caller publishes microphone
                    can_subscribe=True,     # caller hears AI response
                )
            )
            .to_jwt()
        )
        logger.info(
            "Caller token issued: session=%s  identity=%s",
            session_id, identity,
        )
        return token

    def generate_agent_token(self, session_id: str) -> str:
        """
        Generate a JWT for the AI agent joining the room.

        The agent identity is fixed (LIVEKIT_AGENT_IDENTITY from config).
        One agent per room — room name identifies which session it serves.

        Returns
        -------
        str
            Signed JWT string the Python agent passes to room.connect().
        """
        token = (
            AccessToken(self._api_key, self._api_secret)
            .with_identity(settings.LIVEKIT_AGENT_IDENTITY)
            .with_name("AI Help Desk Agent")
            .with_grants(
                VideoGrants(
                    room_join=True,
                    room=session_id,        # room name == session_id
                    can_publish=True,       # agent publishes TTS audio
                    can_subscribe=True,     # agent receives caller mic
                )
            )
            .to_jwt()
        )
        logger.info("Agent token issued: session=%s", session_id)
        return token
