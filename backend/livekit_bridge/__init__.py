"""
livekit/__init__.py — Phase 4: LiveKit Media Transport Package
=================================================================
This package is the transport adapter between LiveKit WebRTC and the
existing AI Help Desk Voice Layer.

Responsibility boundary:
  This package handles:   rooms, participants, tokens, audio transport
  This package NEVER handles: VAD, STT, session state, tickets, validation

Public surface:
  from livekit_bridge.token_manager import TokenManager
  from livekit_bridge.room_manager   import RoomManager
  from livekit_bridge.connection_manager import ConnectionManager
  from livekit_bridge.adapter        import LiveKitAdapter
"""
