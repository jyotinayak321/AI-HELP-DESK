# backend/voice/session.py
# Voice session ka state machine manage karta hai
# Greeting → Service No → Confirm → Complaint → Review → Done

from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field


class VoiceSession(SQLModel, table=True):
    """
    Database table — har voice call ka ek session hoga

    States in order:
    GREETING
        ↓
    CAPTURING_SERVICE_NUMBER   ← user service no bolta hai
        ↓
    CONFIRMING_SERVICE_NUMBER  ← system readback karta hai
        ↓
    CAPTURING_COMPLAINT        ← user complaint bolta hai
        ↓
    OPERATOR_REVIEW            ← operator confirm karta hai
        ↓
    COMPLETED                  ← ticket ban gaya

    OPERATOR_FALLBACK          ← 3 baar galat → operator manually enter kare
    """
    __tablename__ = "voice_sessions"

    # Primary Key — unique session ID (UUID string)
    id: str = Field(primary_key=True)

    # Current state of the voice call
    state: str = Field(default="GREETING")

    # Validated service number
    service_no: Optional[str] = Field(default=None)

    # Full complaint text (from STT)
    complainant_txt: Optional[str] = Field(default=None)

    # Kitni baar galat service number bola
    retries_count: int = Field(default=0)

    # Max retries allowed
    max_retries: int = Field(default=3)

    # Created intake ID (after complaint submitted)
    intake_id: Optional[int] = Field(default=None)

    # Final ticket number
    ticket_number: Optional[str] = Field(default=None)

    # Session start time
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Last update time
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def is_max_retries_exceeded(self) -> bool:
        """3 baar se zyada galat → operator fallback"""
        return self.retries_count >= self.max_retries

    def increment_retry(self):
        """Ek retry add karo"""
        self.retries_count += 1
        self.updated_at = datetime.utcnow()

    def reset_retries(self):
        """Successful validation ke baad reset karo"""
        self.retries_count = 0
        self.updated_at = datetime.utcnow()