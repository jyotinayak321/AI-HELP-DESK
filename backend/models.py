from sqlmodel import SQLModel, Field
from sqlalchemy import Column
from pgvector.sqlalchemy import Vector
from typing import Optional, List
from datetime import datetime
from enum import Enum

class FaultTypeEnum(str, Enum):
    login_access = "login/access"
    performance  = "performance/slow"
    data_error   = "data error"
    total_outage = "total outage"
    partial      = "partial/degraded"
    cosmetic     = "cosmetic/UI"
    other        = "other"

class SeverityEnum(str, Enum):
    critical = "critical"
    high     = "high"
    normal   = "normal"
    low      = "low"

class StatusEnum(str, Enum):
    open     = "open"
    triage   = "triage"
    assigned = "assigned"
    resolved = "resolved"
    closed   = "closed"
    reopened = "reopened"

class DepNatureEnum(str, Enum):
    auth    = "auth"
    data    = "data"
    network = "network"

# TABLE 1: applications
class Application(SQLModel, table=True):
    __tablename__ = "applications"
    id          : Optional[int] = Field(default=None, primary_key=True)
    name        : str = Field(unique=True, max_length=100)
    description : Optional[str] = None
    owning_team : Optional[str] = Field(default=None, max_length=100)
    contact     : Optional[str] = Field(default=None, max_length=200)

# TABLE 2: application_symptoms
class ApplicationSymptom(SQLModel, table=True):
    __tablename__ = "application_symptoms"
    id             : Optional[int] = Field(default=None, primary_key=True)
    application_id : int = Field(foreign_key="applications.id")
    symptom_text   : str
    embedding      : Optional[List[float]] = Field(
                         default=None,
                         sa_column=Column(Vector(1024))
                     )

# TABLE 3: application_purposes
class ApplicationPurpose(SQLModel, table=True):
    __tablename__ = "application_purposes"
    id             : Optional[int] = Field(default=None, primary_key=True)
    application_id : Optional[int] = Field(default=None, foreign_key="applications.id")
    purpose_text   : str
    embedding      : Optional[List[float]] = Field(
                         default=None,
                         sa_column=Column(Vector(1024))
                     )

# TABLE 4: application_dependencies
class ApplicationDependency(SQLModel, table=True):
    __tablename__ = "application_dependencies"
    id               : Optional[int] = Field(default=None, primary_key=True)
    source_app_id    : Optional[int] = Field(default=None, foreign_key="applications.id")
    dependent_app_id : Optional[int] = Field(default=None, foreign_key="applications.id")
    dependency_nature: Optional[str] = Field(default=None, max_length=20)

# TABLE 5: intakes
class Intake(SQLModel, table=True):
    __tablename__ = "intakes"
    id                     : Optional[int] = Field(default=None, primary_key=True)
    raw_text               : str
    operator_id            : Optional[str] = Field(default=None, max_length=50)
    created_at             : Optional[datetime] = Field(default_factory=datetime.utcnow)
    complainant_service_no : Optional[str] = Field(default=None, max_length=20)
    complainant_name       : Optional[str] = Field(default=None, max_length=100)
    complainant_unit       : Optional[str] = Field(default=None, max_length=100)
    complainant_rank       : Optional[str] = Field(default=None, max_length=50)

# TABLE 6: tickets
class Ticket(SQLModel, table=True):
    __tablename__ = "tickets"
    ticket_number          : str = Field(primary_key=True, max_length=20)
    intake_id              : Optional[int] = Field(default=None, foreign_key="intakes.id")
    complainant_id         : Optional[str] = Field(default=None, max_length=50)
    primary_application_id : Optional[int] = Field(default=None, foreign_key="applications.id")
    status                 : Optional[str] = Field(default="open", max_length=20)
    fault_type             : Optional[str] = Field(default=None, max_length=50)
    severity               : Optional[str] = Field(default="medium", max_length=20)
    complainant_service_no : Optional[str] = Field(default=None, max_length=20)
    complainant_rank       : Optional[str] = Field(default=None, max_length=50)
    complainant_unit       : Optional[str] = Field(default=None, max_length=100)

# TABLE 7: ticket_related_apps
class TicketRelatedApp(SQLModel, table=True):
    __tablename__ = "ticket_related_apps"
    ticket_number          : str = Field(foreign_key="tickets.ticket_number", primary_key=True, max_length=20)
    related_application_id : int = Field(foreign_key="applications.id", primary_key=True)

# TABLE 8: learning_examples
class LearningExample(SQLModel, table=True):
    __tablename__ = "learning_examples"
    id               : Optional[int] = Field(default=None, primary_key=True)
    ticket_number    : Optional[str] = Field(default=None, foreign_key="tickets.ticket_number", max_length=20)
    raw_text         : str
    text_embedding   : Optional[List[float]] = Field(
                           default=None,
                           sa_column=Column(Vector(1024))
                       )
    predicted_app_id : Optional[int] = Field(default=None, foreign_key="applications.id")
    confirmed_app_id : Optional[int] = Field(default=None, foreign_key="applications.id")

# TABLE 9: ticket_history
class TicketHistory(SQLModel, table=True):
    __tablename__ = "ticket_history"
    id            : Optional[int] = Field(default=None, primary_key=True)
    ticket_number : Optional[str] = Field(default=None, foreign_key="tickets.ticket_number", max_length=20)
    changed_by    : Optional[str] = Field(default=None, max_length=50)
    old_status    : Optional[str] = Field(default=None, max_length=20)
    new_status    : Optional[str] = Field(default=None, max_length=20)
    notes         : Optional[str] = None
    changed_at    : Optional[datetime] = Field(default_factory=datetime.utcnow)