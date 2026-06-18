from pydantic import BaseModel
from typing import Optional, List
from models import FaultTypeEnum, SeverityEnum, StatusEnum

class IntakeRequest(BaseModel):
    raw_text               : str
    complainant_service_no : str
    complainant_identity   : Optional[str] = None

class CandidateApp(BaseModel):
    application_id   : int
    name             : str
    confidence_score : float
    is_primary       : bool
    expansion_reason : Optional[str] = None

class IntakeResponse(BaseModel):
    is_repeat_caller       : bool
    existing_ticket_number : Optional[str] = None
    fault_type_proposal    : FaultTypeEnum
    severity_proposal      : SeverityEnum
    candidates             : List[CandidateApp]

class TicketConfirmRequest(BaseModel):
    complainant_service_no     : str
    complainant_identity       : Optional[str] = None
    original_complaint_text    : str
    confirmed_primary_app_id   : int
    confirmed_fault_type       : FaultTypeEnum
    confirmed_severity         : SeverityEnum
    predicted_primary_app_id   : Optional[int] = None
    predicted_fault_type       : Optional[FaultTypeEnum] = None
    predicted_severity         : Optional[SeverityEnum] = None
    related_app_ids            : List[int] = []
    operator_notes             : Optional[str] = None

class TicketStatusUpdate(BaseModel):
    status           : StatusEnum
    notes            : Optional[str] = None
    resolving_action : Optional[str] = None

class TicketCreateResponse(BaseModel):
    ticket_number : str
    status        : str
    routed_to     : str
    message       : str
