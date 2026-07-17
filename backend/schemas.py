"""
AI Help Desk — Pydantic Schemas
================================
Request/Response validation models for all API endpoints.
Person 2 owns this file.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# =====================================================================
# ENUMS / CONSTANTS (Matching the DB schema values)
# =====================================================================

VALID_FAULT_TYPES = [
    "login/access",
    "performance/slow",
    "data error",
    "total outage",
    "partial/degraded",
    "cosmetic/UI",
    "other",
]

VALID_SEVERITIES = ["critical", "high", "normal", "low"]

VALID_STATUSES = ["open", "triage", "assigned", "in_progress", "resolved", "closed", "reopened"]

VALID_DEPENDENCY_NATURES = [
    "login/access", 
    "performance/slow", 
    "data error", 
    "total outage", 
    "partial/degraded", 
    "cosmetic/UI", 
    "other"
]


# =====================================================================
# APPLICATION SCHEMAS (Used by Person 1's admin.py, defined here for shared use)
# =====================================================================

class ApplicationCreate(BaseModel):
    """Schema for registering a new application."""
    name: str = Field(..., max_length=100, examples=["Leave & Attendance Portal"])
    description: str = Field(..., examples=["Employee portal for marking attendance."])
    owning_team: str = Field(..., max_length=100, examples=["HR Tech Services"])
    contact: str = Field(..., max_length=200, examples=["hr-tech@company.com"])


class ApplicationResponse(BaseModel):
    """Schema for returning an application record."""
    id: int
    name: str
    description: str
    owning_team: str
    contact: str

    model_config = {"from_attributes": True}


class PurposeCreate(BaseModel):
    """Schema for adding a purpose to an application."""
    application_id: int
    purpose_text: str


class SymptomCreate(BaseModel):
    """Schema for adding a symptom to an application."""
    application_id: int
    symptom_text: str


class DependencyCreate(BaseModel):
    """Schema for creating an application dependency link."""
    source_app_id: int
    dependent_app_id: int
    dependency_nature: str = Field(..., examples=["auth"])


class DependencyResponse(BaseModel):
    """Schema for returning a dependency record."""
    id: int
    source_app_id: int
    dependent_app_id: int
    dependency_nature: str

    model_config = {"from_attributes": True}


# =====================================================================
# INTAKE SCHEMAS (POST /api/intakes)
# =====================================================================

class IntakeRequest(BaseModel):
    """
    What the operator sends when a caller describes their problem.
    Satisfies R-5 (Accept complaint text) and R-7 (Record service number).
    """
    raw_text: str = Field(
        ...,
        min_length=5,
        examples=["Mera leave portal kaam nahi kar raha, login nahi ho raha hai"],
    )
    complainant_service_no: str = Field(
        ...,
        max_length=20,
        examples=["SVC-12345"],
    )
    complainant_name: str = Field(
        default="",
        max_length=100,
        examples=["Suresh Kumar"],
    )
    complainant_unit: str = Field(
        default="",
        max_length=100,
        examples=["Admin Wing"],
    )
    complainant_rank: str = Field(
        default="",
        max_length=50,
        examples=["Sergeant"],
    )
    operator_id: str = Field(
        default="system",
        max_length=50,
        examples=["OP-001"],
    )


class CandidateApp(BaseModel):
    """
    A single candidate application returned by the AI pipeline.
    Satisfies R-9 (Never a forced single guess — returns ranked list).
    """
    application_id: int
    application_name: str
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    is_primary: bool = False
    expansion_reason: Optional[str] = Field(
        default=None,
        examples=["Expanded via 'auth' dependency of Leave Portal"],
    )


class DuplicateInfo(BaseModel):
    """Information about a potential duplicate ticket."""
    ticket_number: str
    complainant_service_no: str
    text_snippet: str
    status: str
    is_same_user: bool

class IntakeResponse(BaseModel):
    """
    The AI's proposal returned to the operator for confirmation.
    Satisfies R-13 (Operator reviews before ticket creation).
    """
    intake_id: int
    corrected_text: Optional[str] = None
    is_repeat_caller: bool = False
    potential_duplicates: list[DuplicateInfo] = Field(default_factory=list)
    fault_type_proposal: str = Field(..., examples=["login/access"])
    severity_proposal: str = Field(..., examples=["high"])
    candidates: list[CandidateApp] = Field(default_factory=list)


# =====================================================================
# TICKET CONFIRM SCHEMAS (POST /api/tickets/confirm)
# =====================================================================

class TicketConfirmRequest(BaseModel):
    """
    Sent when the operator clicks 'Confirm & Create Ticket'.
    Captures the confirmed values vs. what the AI predicted (R-22).
    """
    intake_id: int
    confirmed_app_id: Optional[int] = Field(
        default=None,
        description="The app the operator confirmed as primary. None means the operator "
                    "rejected all candidates (R-17) — the ticket is routed to triage "
                    "instead of forcing a wrong label.",
    )
    related_app_ids: list[int] = Field(
        default_factory=list,
        description="Additional affected applications",
    )
    confirmed_fault_type: str = Field(..., examples=["login/access"])
    confirmed_severity: str = Field(..., examples=["high"])
    operator_notes: str = Field(default="", examples=["User confirmed SSO was down"])
    edited_raw_text: Optional[str] = Field(default=None, description="The operator's manually edited complaint text")
    voice_session_id: Optional[str] = Field(
        default=None,
        description="If this ticket originated from a voice call, the voice session ID "
                    "(R-42) so the call's FSM can advance to ASK_ANOTHER_COMPLAINT.",
    )


    # What the AI originally predicted (for learning loop comparison)
    predicted_app_id: Optional[int] = None
    predicted_fault_type: Optional[str] = None
    predicted_severity: Optional[str] = None


class TicketConfirmResponse(BaseModel):
    """Returned after a ticket is successfully created."""
    ticket_number: str = Field(..., examples=["TIC-202606-0001"])
    status: str = "open"
    primary_application_name: str
    fault_type: str
    severity: str
    routed_to_team: str
    message: str = "Ticket created successfully"

    # Populated only when the request carried a voice_session_id and the
    # voice call FSM successfully advanced (R-42), so the frontend knows
    # whether to loop back into the voice panel for another complaint.
    voice_session_id: Optional[str] = None
    voice_next_state: Optional[str] = None
    voice_prompt_text: Optional[str] = None


# =====================================================================
# TICKET LIST / DASHBOARD SCHEMAS (GET /api/tickets)
# =====================================================================

class TicketResponse(BaseModel):
    """Schema for returning a single ticket in list/detail views."""
    ticket_number: str
    complainant_service_no: str
    complainant_rank: str = ""
    complainant_unit: str = ""
    primary_application_id: Optional[int] = None
    primary_application_name: Optional[str] = None
    original_complaint_text: Optional[str] = None
    status: str
    fault_type: str
    severity: str
    assignee_id: Optional[str] = None
    dependencies: List[dict] = Field(default_factory=list)
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MassOutageAlert(BaseModel):
    """
    Fired when >10 tickets hit the same application in the last hour.
    Satisfies R-21 (Mass-Outage Detection).
    """
    application_id: int
    application_name: str
    ticket_count: int
    time_window_minutes: int = 60
    alert_message: str


class TicketListResponse(BaseModel):
    """Wraps the list of tickets with optional mass-outage alerts."""
    tickets: list[TicketResponse] = Field(default_factory=list)
    total_count: int = 0
    mass_outage_alerts: list[MassOutageAlert] = Field(default_factory=list)


# =====================================================================
# TICKET UPDATE SCHEMAS (PATCH /api/tickets/{ticket_number})
# =====================================================================

class TicketUpdateRequest(BaseModel):
    """
    Used to update ticket status and optionally assign it.
    R-18/R-19: Moving to 'closed' REQUIRES notes to be filled in.
    """
    new_status: str = Field(..., examples=["resolved"])
    notes: str = Field(
        default="",
        description="Required when closing a ticket (R-19). Describes the resolution action.",
    )
    changed_by: str = Field(default="system", examples=["OP-001"])
    assignee_id: Optional[str] = Field(default=None, examples=["12345P"], description="Service number of the operator taking ownership")


class TicketUpdateResponse(BaseModel):
    """Returned after a ticket status update."""
    ticket_number: str
    old_status: str
    new_status: str
    message: str


# =====================================================================
# HISTORY SCHEMA (for reference / potential future GET endpoint)
# =====================================================================

class TicketHistoryResponse(BaseModel):
    """A single audit trail entry for a ticket."""
    id: int
    ticket_number: str
    changed_by: Optional[str] = None
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    notes: Optional[str] = None
    changed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# =====================================================================
# R-23: SIMILAR RESOLUTION SCHEMA
# =====================================================================

class SimilarResolution(BaseModel):
    """A past resolution note that is semantically similar to the current ticket."""
    ticket_number: str
    notes: str
    changed_by: Optional[str] = None
    changed_at: Optional[datetime] = None
    similarity_score: float


# =====================================================================
# R-14a: MULTI-TICKET CONFIRM SCHEMAS
# =====================================================================

class TicketConfirmItem(BaseModel):
    """
    A single ticket to create within a multi-fault intake confirmation.
    """
    confirmed_app_id: int = Field(..., description="The app confirmed as primary for this sub-ticket")
    related_app_ids: list[int] = Field(default_factory=list)
    confirmed_fault_type: str = Field(..., examples=["login/access"])
    confirmed_severity: str = Field(..., examples=["high"])
    operator_notes: str = Field(default="")
    edited_raw_text: Optional[str] = None
    predicted_app_id: Optional[int] = None
    predicted_fault_type: Optional[str] = None
    predicted_severity: Optional[str] = None


class MultiTicketConfirmRequest(BaseModel):
    """
    R-14a: One intake can produce multiple tickets for separate faults.
    """
    intake_id: int
    tickets: list[TicketConfirmItem] = Field(..., min_length=1)


class MultiTicketConfirmResponse(BaseModel):
    """Returned after multi-ticket creation."""
    created_tickets: list[TicketConfirmResponse]
    message: str
