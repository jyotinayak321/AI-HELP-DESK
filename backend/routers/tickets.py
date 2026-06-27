"""
AI Help Desk â€” Tickets Router
===============================
OWNER: Person 2
The heaviest file in the project. Handles the full ticket lifecycle:

  POST /api/intakes          â€” Accept complaint, check repeats, call AI, return proposals
  POST /api/tickets/confirm  â€” Create ticket from confirmed proposal
  GET  /api/tickets          â€” List/filter tickets + mass-outage detection
  PATCH /api/tickets/{tn}    â€” Update status, enforce closure rules, log history

Requirement coverage: R-5, R-6, R-7, R-9, R-10, R-13, R-14, R-15,
                      R-16, R-18, R-19, R-20, R-20a, R-21, R-22, R-23
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, col, func, text
import datetime as dt_lib
from datetime import timedelta, timezone
from typing import Optional

from database import get_session
from models import (
    Application,
    Intake,
    Ticket,
    TicketRelatedApp,
    TicketHistory,
    LearningExample,
)
from schemas import (
    IntakeRequest,
    IntakeResponse,
    CandidateApp,
    DuplicateInfo,
    TicketConfirmRequest,
    TicketConfirmResponse,
    TicketConfirmItem,
    MultiTicketConfirmRequest,
    MultiTicketConfirmResponse,
    TicketResponse,
    TicketListResponse,
    TicketUpdateRequest,
    TicketUpdateResponse,
    TicketHistoryResponse,
    MassOutageAlert,
    SimilarResolution,
    VALID_FAULT_TYPES,
    VALID_SEVERITIES,
    VALID_STATUSES,
)

from services.embedder import TextEmbedder
from services.classifier import TicketClassifier
from services.search import ApplicationSearchEngine
from services.dependencies import ApplicationDependencyEngine

# Initialize the global instances so they don't load models on every request
embedder = TextEmbedder()
classifier = TicketClassifier()
search_engine = ApplicationSearchEngine()
dependency_engine = ApplicationDependencyEngine()

router = APIRouter()


# =====================================================================
# HELPER: Generate Ticket Number â€” TIC-YYYYMM-XXXX
# =====================================================================

def _generate_ticket_number(session: Session) -> str:
    """
    Generates the next sequential ticket number in the format TIC-YYYYMM-XXXX.
    Queries the DB to find the highest existing number for the current month.
    """
    now = dt_lib.datetime.now(timezone.utc)
    prefix = f"TIC-{now.strftime('%Y%m')}-"

    # Find the highest ticket number for this month
    statement = (
        select(Ticket.ticket_number)
        .where(col(Ticket.ticket_number).startswith(prefix))
        .order_by(col(Ticket.ticket_number).desc())
    )
    result = session.exec(statement).first()

    if result:
        # Extract the sequence number and increment
        last_seq = int(result.split("-")[-1])
        next_seq = last_seq + 1
    else:
        next_seq = 1

    return f"{prefix}{next_seq:04d}"


# =====================================================================
# 1. POST /api/intakes â€” Accept complaint & return AI proposals
# =====================================================================
# Requirements: R-5 (Accept text), R-6 (Operator submits form),
#               R-7 (Record service number), R-9 (Ranked candidates),
#               R-10 (Dependency expansion), R-13 (Operator reviews),
#               R-20a (Repeat-caller detection)

@router.post("/intakes", response_model=IntakeResponse)
def create_intake(
    request: IntakeRequest,
    session: Session = Depends(get_session),
):
    """
    Step 1 of the ticket creation flow.
    Accepts raw complaint text, runs AI classification, and returns
    proposals for the operator to review before confirming.
    """

    # -----------------------------------------------------------------
    # 1a. Save the raw complaint to complaint_intake table
    # -----------------------------------------------------------------
    intake = Intake(
        raw_text=request.raw_text,
        operator_id=request.operator_id,
        complainant_service_no=request.complainant_service_no,
        complainant_name=request.complainant_name,
        complainant_unit=request.complainant_unit,
        complainant_rank=request.complainant_rank,
    )
    session.add(intake)
    session.commit()
    session.refresh(intake)

    # -----------------------------------------------------------------
    # 1b. AI PIPELINE â€” Call Team B's functions
    # -----------------------------------------------------------------

    # Step 1: Generate embedding vector from complaint text
    embedding = embedder.get_embedding(request.raw_text)

    # -----------------------------------------------------------------
    # 1c. SEMANTIC DUPLICATE & MASS OUTAGE CHECK
    # -----------------------------------------------------------------
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
    
    # Only look at tickets created in the last 4 hours to prevent stale alerts
    time_limit = dt_lib.datetime.now(timezone.utc) - timedelta(hours=4)
    
    duplicate_query = text("""
        SELECT t.ticket_number, t.complainant_service_no, l.raw_text, t.status, (l.text_embedding <=> :embedding) AS distance
        FROM tickets t
        JOIN learning_examples l ON t.ticket_number = l.ticket_number
        WHERE t.status != 'resolved' 
          AND t.created_at >= :time_limit
          AND (l.text_embedding <=> :embedding) < 0.20
        ORDER BY distance ASC
        LIMIT 5
    """)
    dupes = session.execute(duplicate_query, {
        "embedding": embedding_str, 
        "time_limit": time_limit
    }).fetchall()
    
    potential_duplicates = []
    is_repeat = False
    
    for row in dupes:
        is_same = (row.complainant_service_no == request.complainant_service_no)
        dist = float(row.distance)
        
        # Dual thresholds: Looser for same user (0.20) to catch repeat complaints,
        # Tighter for different user (0.10) to prevent false-positive mass outages.
        if is_same and dist < 0.20:
            is_repeat = True
            
        if (is_same and dist < 0.20) or (not is_same and dist < 0.10):
            snippet = row.raw_text[:80] + "..." if len(row.raw_text) > 80 else row.raw_text
            potential_duplicates.append({
                "ticket_number": row.ticket_number,
                "complainant_service_no": row.complainant_service_no,
                "text_snippet": snippet,
                "status": row.status,
                "is_same_user": is_same
            })

    # Step 2: Classify fault type and severity using Hybrid Strategy
    fault_type = classifier.classify_fault_type(request.raw_text)
    severity = classifier.classify_severity(request.raw_text)

    # Step 3: Find candidate applications via vector similarity search
    raw_candidates = search_engine.search_candidates(session, embedding)
    
    enriched_candidates = []
    for cand in raw_candidates:
        app_obj = session.get(Application, cand["application_id"])
        if app_obj:
            enriched_candidates.append({
                "application_id": app_obj.id,
                "application_name": app_obj.name,
                "confidence_score": cand["score"]
            })

    # Step 4: Expand dependencies based on fault type (R-10)
    primary_candidate = enriched_candidates[0] if enriched_candidates else None
    expanded_deps = []
    if primary_candidate:
        dep_ids = dependency_engine.expand_dependencies(
            db_session=session,
            primary_app_id=primary_candidate["application_id"],
            fault_type=fault_type,
        )
        for d_id in dep_ids:
            d_app = session.get(Application, d_id)
            if d_app:
                expanded_deps.append({
                    "application_id": d_id,
                    "application_name": d_app.name,
                    "expansion_reason": f"Cascade from {fault_type}"
                })

    # -----------------------------------------------------------------
    # 1d. BUILD THE RESPONSE â€” Merge candidates + expansions
    # -----------------------------------------------------------------
    candidates: list[CandidateApp] = []

    # Add direct candidates from vector search
    for i, cand in enumerate(enriched_candidates):
        candidates.append(
            CandidateApp(
                application_id=cand["application_id"],
                application_name=cand["application_name"],
                confidence_score=round(cand["confidence_score"], 4),
                is_primary=(i == 0),  # Top result is marked as primary
            )
        )

    # Add dependency-expanded candidates (avoid duplicates)
    existing_app_ids = {c.application_id for c in candidates}
    for dep in expanded_deps:
        if dep["application_id"] not in existing_app_ids:
            candidates.append(
                CandidateApp(
                    application_id=dep["application_id"],
                    application_name=dep["application_name"],
                    confidence_score=0.0,  # Expansion â€” no direct score
                    is_primary=False,
                    expansion_reason=dep.get("expansion_reason"),
                )
            )

    return IntakeResponse(
        intake_id=intake.id,
        is_repeat_caller=is_repeat,
        potential_duplicates=potential_duplicates,
        fault_type_proposal=fault_type,
        severity_proposal=severity,
        candidates=candidates,
    )


# =====================================================================
# 2. POST /api/tickets/confirm â€” Create ticket from confirmed proposal
# =====================================================================
# Requirements: R-14 (Create ticket), R-15 (Related apps junction),
#               R-16 (Route to owning team), R-22 (Save learning example)

@router.post("/tickets/confirm", response_model=TicketConfirmResponse)
def confirm_ticket(
    request: TicketConfirmRequest,
    session: Session = Depends(get_session),
):
    """
    Step 2 of the ticket creation flow.
    Operator has reviewed the AI proposal, possibly corrected it,
    and clicked 'Confirm & Create Ticket'.
    """

    # -----------------------------------------------------------------
    # Validate inputs
    # -----------------------------------------------------------------
    if request.confirmed_fault_type not in VALID_FAULT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid fault_type: '{request.confirmed_fault_type}'. Must be one of {VALID_FAULT_TYPES}",
        )
    if request.confirmed_severity not in VALID_SEVERITIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid severity: '{request.confirmed_severity}'. Must be one of {VALID_SEVERITIES}",
        )

    # Look up the confirmed application
    app = session.get(Application, request.confirmed_app_id)
    if not app:
        raise HTTPException(status_code=404, detail=f"Application ID {request.confirmed_app_id} not found.")

    # Look up the intake record
    intake = session.get(Intake, request.intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail=f"Intake ID {request.intake_id} not found.")

    # -----------------------------------------------------------------
    # Generate ticket number: TIC-YYYYMM-XXXX
    # -----------------------------------------------------------------
    ticket_number = _generate_ticket_number(session)

    # -----------------------------------------------------------------
    # R-14: Insert into tickets table
    # -----------------------------------------------------------------
    ticket = Ticket(
        ticket_number=ticket_number,
        intake_id=intake.id,
        primary_application_id=request.confirmed_app_id,
        status="open",
        fault_type=request.confirmed_fault_type,
        severity=request.confirmed_severity,
        complainant_service_no=intake.complainant_service_no,
        complainant_rank=intake.complainant_rank,
        complainant_unit=intake.complainant_unit,
    )
    session.add(ticket)
    session.flush()  # Force INSERT into tickets table so foreign keys pass

    # -----------------------------------------------------------------
    # R-15: Insert related applications into junction table
    # -----------------------------------------------------------------
    for related_id in request.related_app_ids:
        if related_id != request.confirmed_app_id:  # Don't duplicate primary
            related_app = session.get(Application, related_id)
            if related_app:
                rel = TicketRelatedApp(
                    ticket_number=ticket_number,
                    related_application_id=related_id,
                )
                session.add(rel)

    # -----------------------------------------------------------------
    # R-22: Save to learning_examples (prediction vs confirmed)
    # This feeds the AI learning loop.
    # -----------------------------------------------------------------
    embedding = embedder.get_embedding(intake.raw_text)
    learning_entry = LearningExample(
        ticket_number=ticket_number,
        raw_text=intake.raw_text,
        text_embedding=embedding,
        predicted_app_id=request.predicted_app_id,
        confirmed_app_id=request.confirmed_app_id,
        predicted_fault_type=request.predicted_fault_type,
        confirmed_fault_type=request.confirmed_fault_type,
        predicted_severity=request.predicted_severity,
        confirmed_severity=request.confirmed_severity,
    )
    session.add(learning_entry)

    # -----------------------------------------------------------------
    # R-16: Route to the owning team (stored in response for frontend)
    # -----------------------------------------------------------------
    routed_to = app.owning_team

    # -----------------------------------------------------------------
    # Log initial ticket history entry
    # -----------------------------------------------------------------
    history = TicketHistory(
        ticket_number=ticket_number,
        changed_by="system",
        old_status="",
        new_status="open",
        notes=f"Ticket created. Routed to {routed_to}. "
              f"Operator notes: {request.operator_notes}" if request.operator_notes else
              f"Ticket created. Routed to {routed_to}.",
    )
    session.add(history)

    # Commit everything in one transaction
    session.commit()

    return TicketConfirmResponse(
        ticket_number=ticket_number,
        status="open",
        primary_application_name=app.name,
        fault_type=request.confirmed_fault_type,
        severity=request.confirmed_severity,
        routed_to_team=routed_to,
        message=f"Ticket {ticket_number} created and routed to {routed_to}.",
    )


# =====================================================================
# 3. GET /api/tickets â€” List / filter tickets + mass-outage detection
# =====================================================================
# Requirements: R-20 (Dashboard list), R-21 (Mass-Outage Detection)

@router.get("/tickets", response_model=TicketListResponse)
def list_tickets(
    status: Optional[str] = Query(None, description="Filter by status"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    app_id: Optional[int] = Query(None, description="Filter by primary application"),
    date_from: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    search: Optional[str] = Query(None, description="Search keyword"),
    team: Optional[str] = Query(None, description="Filter by owning team name"),
    complainant_service_no: Optional[str] = Query(None, description="Filter by service number"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
):
    """
    Returns a filtered list of tickets plus any mass-outage alerts.
    """

    # -----------------------------------------------------------------
    # Build filtered query
    # -----------------------------------------------------------------
    print(f"DEBUG FILTERS: status={status}, severity={severity}, app_id={app_id}, date_from={date_from}, date_to={date_to}, search={search}")
    statement = select(Ticket)

    if status:
        statement = statement.where(Ticket.status == status)
    if severity:
        statement = statement.where(Ticket.severity == severity)
    if app_id:
        statement = statement.where(Ticket.primary_application_id == app_id)
    if complainant_service_no:
        statement = statement.where(Ticket.complainant_service_no == complainant_service_no)

    # R-16: Filter by owning team (join to applications)
    if team:
        team_app_ids = session.exec(
            select(Application.id).where(col(Application.owning_team).ilike(f"%{team}%"))
        ).all()
        statement = statement.where(col(Ticket.primary_application_id).in_(team_app_ids))
    
    if date_from:
        try:
            df = dt_lib.datetime.strptime(date_from, "%Y-%m-%d")
            statement = statement.where(Ticket.created_at >= df)
        except ValueError:
            pass
            
    if date_to:
        try:
            # Add one day to include the whole end date
            dt_obj = dt_lib.datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)
            statement = statement.where(Ticket.created_at < dt_obj)
        except ValueError:
            pass

    if search:
        # Simple search across ticket number, or just basic string match
        statement = statement.where(col(Ticket.ticket_number).contains(search))

    # Get total count before pagination
    count_statement = select(func.count()).select_from(statement.subquery())
    total_count = session.exec(count_statement).one()

    # Apply pagination and ordering
    statement = statement.order_by(col(Ticket.created_at).desc()).offset(skip).limit(limit)
    tickets = session.exec(statement).all()

    # -----------------------------------------------------------------
    # Build ticket responses (resolve app name from FK)
    # -----------------------------------------------------------------
    ticket_responses = []
    for t in tickets:
        app_name = None
        if t.primary_application_id:
            app = session.get(Application, t.primary_application_id)
            app_name = app.name if app else None

        # Resolve original complaint text from the linked intake
        complaint_text = None
        if t.intake_id:
            intake = session.get(Intake, t.intake_id)
            complaint_text = intake.raw_text if intake else None

        # Resolve cascaded dependencies
        deps = []
        if t.primary_application_id and t.fault_type:
            dep_ids = dependency_engine.expand_dependencies(
                db_session=session,
                primary_app_id=t.primary_application_id,
                fault_type=t.fault_type,
            )
            for d_id in dep_ids:
                d_app = session.get(Application, d_id)
                if d_app:
                    deps.append({
                        "application_id": d_id,
                        "application_name": d_app.name,
                        "dependency_nature": t.fault_type
                    })

        ticket_responses.append(
            TicketResponse(
                ticket_number=t.ticket_number,
                complainant_service_no=t.complainant_service_no or "",
                complainant_rank=t.complainant_rank or "",
                complainant_unit=t.complainant_unit or "",
                primary_application_id=t.primary_application_id,
                primary_application_name=app_name,
                original_complaint_text=complaint_text,
                status=t.status or "open",
                fault_type=t.fault_type or "",
                severity=t.severity or "",
                assignee_id=t.assignee_id,
                dependencies=deps,
                created_at=t.created_at,
            )
        )

    # -----------------------------------------------------------------
    # R-21: MASS-OUTAGE DETECTION
    # Check if any single application has >10 tickets in the last hour.
    # -----------------------------------------------------------------
    one_hour_ago = dt_lib.datetime.now(timezone.utc) - timedelta(hours=1)

    outage_statement = (
        select(
            Ticket.primary_application_id,
            func.count(Ticket.ticket_number).label("ticket_count"),
        )
        .where(
            Ticket.created_at >= one_hour_ago,
            col(Ticket.status).in_(["open", "assigned", "in_progress"]),
            Ticket.primary_application_id.isnot(None),
        )
        .group_by(Ticket.primary_application_id)
        .having(func.count(Ticket.ticket_number) > 10)
    )
    outage_results = session.exec(outage_statement).all()

    mass_outage_alerts = []
    for app_id, count in outage_results:
        app = session.get(Application, app_id)
        if app:
            mass_outage_alerts.append(
                MassOutageAlert(
                    application_id=app_id,
                    application_name=app.name,
                    ticket_count=count,
                    time_window_minutes=60,
                    alert_message=(
                        f"âš ï¸ MASS OUTAGE DETECTED: {app.name} has {count} "
                        f"open tickets in the last 60 minutes. "
                        f"Contact {app.owning_team} immediately."
                    ),
                )
            )

    return TicketListResponse(
        tickets=ticket_responses,
        total_count=total_count,
        mass_outage_alerts=mass_outage_alerts,
    )


# =====================================================================
# 4. PATCH /api/tickets/{ticket_number} â€” Update status + audit trail
# =====================================================================
# Requirements: R-18 (Status transitions), R-19 (Closure requires notes),
#               R-23 (Log resolution into history)

@router.patch("/tickets/{ticket_number}", response_model=TicketUpdateResponse)
def update_ticket(
    ticket_number: str,
    request: TicketUpdateRequest,
    session: Session = Depends(get_session),
):
    """
    Updates a ticket's status. Enforces business rules:
      - Moving to 'closed' REQUIRES notes (R-19)
      - Every status change is logged to ticket_history (R-23)
    """

    # -----------------------------------------------------------------
    # Find the ticket
    # -----------------------------------------------------------------
    ticket = session.exec(
        select(Ticket).where(Ticket.ticket_number == ticket_number)
    ).first()

    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_number} not found.")

    # -----------------------------------------------------------------
    # Validate new status
    # -----------------------------------------------------------------
    if request.new_status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: '{request.new_status}'. Must be one of {VALID_STATUSES}",
        )

    # Cannot update a ticket that is already closed
    if ticket.status == "closed":
        raise HTTPException(
            status_code=400,
            detail=f"Ticket {ticket_number} is already closed. Cannot update.",
        )

    # -----------------------------------------------------------------
    # R-19: Enforce that closing requires notes
    # -----------------------------------------------------------------
    if request.new_status == "closed" and not request.notes.strip():
        raise HTTPException(
            status_code=400,
            detail="Cannot close a ticket without providing resolution notes (R-19). "
                   "Please describe the resolving action in the 'notes' field.",
        )

    # -----------------------------------------------------------------
    # Save old status for audit trail
    # -----------------------------------------------------------------
    old_status = ticket.status

    # -----------------------------------------------------------------
    # R-19: Apply assignee if provided
    # -----------------------------------------------------------------
    if request.assignee_id is not None:
        ticket.assignee_id = request.assignee_id

    # -----------------------------------------------------------------
    # Update the ticket status
    # -----------------------------------------------------------------
    ticket.status = request.new_status
    session.add(ticket)

    # -----------------------------------------------------------------
    # R-23: Embed resolution notes when closing/resolving
    # -----------------------------------------------------------------
    resolution_embedding = None
    if request.new_status in ("resolved", "closed") and request.notes.strip():
        resolution_embedding = embedder.get_embedding(request.notes)

    # -----------------------------------------------------------------
    # Log the status change into ticket_history
    # -----------------------------------------------------------------
    history_entry = TicketHistory(
        ticket_number=ticket_number,
        changed_by=request.changed_by,
        old_status=old_status,
        new_status=request.new_status,
        notes=request.notes,
        resolution_embedding=resolution_embedding,
    )
    session.add(history_entry)

    session.commit()

    return TicketUpdateResponse(
        ticket_number=ticket_number,
        old_status=old_status,
        new_status=request.new_status,
        message=f"Ticket {ticket_number} updated: {old_status} â†’ {request.new_status}",
    )


# =====================================================================
# 5. GET /api/tickets/{tn}/similar-resolutions â€” R-23
# =====================================================================

@router.get("/tickets/{ticket_number}/similar-resolutions", response_model=list[SimilarResolution])
def get_similar_resolutions(
    ticket_number: str,
    session: Session = Depends(get_session),
):
    """
    R-23: Complaint-to-Complaint matching.
    Steps:
      1. Get the embedding of the CURRENT ticket's complaint.
      2. Find past COMPLAINTS (in learning_examples) with similar embeddings.
         These past tickets must already be resolved/closed.
      3. For each matching past ticket, fetch the resolution note from ticket_history.
      4. Return those notes â€” telling Operator B "here's how a similar problem was fixed."
    """
    # Step 1: Get the current ticket's complaint embedding
    le = session.exec(
        select(LearningExample).where(LearningExample.ticket_number == ticket_number)
    ).first()

    if not le or le.text_embedding is None:
        return []

    embedding_str = "[" + ",".join(map(str, le.text_embedding)) + "]"

    # Step 2 & 3:
    # - Join learning_examples (for complaint similarity) with tickets (to check status)
    # - and ticket_history (to get resolution notes)
    # - Only match tickets that are actually resolved/closed (i.e., have a resolution note)
    # - Exclude the current ticket itself
    resolution_query = text("""
        SELECT
            le_past.ticket_number,
            th.notes,
            th.changed_by,
            th.changed_at,
            (le_past.text_embedding <=> :embedding) AS distance
        FROM learning_examples le_past
        JOIN tickets t ON t.ticket_number = le_past.ticket_number
        JOIN ticket_history th ON th.ticket_number = le_past.ticket_number
        WHERE le_past.text_embedding IS NOT NULL
          AND le_past.ticket_number != :current_tn
          AND t.status IN ('resolved', 'closed')
          AND th.notes IS NOT NULL
          AND th.notes != ''
          AND th.new_status IN ('resolved', 'closed')
        ORDER BY distance ASC
        LIMIT 3
    """)
    rows = session.execute(resolution_query, {
        "embedding": embedding_str,
        "current_tn": ticket_number
    }).fetchall()

    # Only return results that are meaningfully similar (distance < 0.12, i.e. >88% match)
    return [
        SimilarResolution(
            ticket_number=row.ticket_number,
            notes=row.notes,
            changed_by=row.changed_by,
            changed_at=row.changed_at,
            similarity_score=round(max(0.0, 1.0 - float(row.distance)), 3),
        )
        for row in rows
        if float(row.distance) < 0.12
    ]


# =====================================================================
# 5b. GET /api/tickets/{tn}/history â€” Audit Trail
# =====================================================================

@router.get("/tickets/{ticket_number}/history", response_model=list[TicketHistoryResponse])
def get_ticket_history(
    ticket_number: str,
    session: Session = Depends(get_session),
):
    """
    Returns the full chronological audit trail for a ticket.
    Includes all status changes and resolution notes.
    """
    ticket = session.exec(
        select(Ticket).where(Ticket.ticket_number == ticket_number)
    ).first()
    if not ticket:
        raise HTTPException(status_code=404, detail=f"Ticket {ticket_number} not found.")

    history = session.exec(
        select(TicketHistory)
        .where(TicketHistory.ticket_number == ticket_number)
        .order_by(col(TicketHistory.changed_at).asc())
    ).all()

    return [
        TicketHistoryResponse(
            id=h.id,
            ticket_number=h.ticket_number,
            changed_by=h.changed_by,
            old_status=h.old_status,
            new_status=h.new_status,
            notes=h.notes,
            changed_at=h.changed_at,
        )
        for h in history
    ]


# =====================================================================
# 6. POST /api/tickets/confirm-multi â€” R-14a
# =====================================================================

@router.post("/tickets/confirm-multi", response_model=MultiTicketConfirmResponse)
def confirm_multi_ticket(
    request: MultiTicketConfirmRequest,
    session: Session = Depends(get_session),
):
    """
    R-14a: Create multiple tickets from a single intake when the operator
    identifies genuinely separate faults in one complaint.
    """
    intake = session.get(Intake, request.intake_id)
    if not intake:
        raise HTTPException(status_code=404, detail=f"Intake {request.intake_id} not found.")

    embedding = embedder.get_embedding(intake.raw_text)
    created = []

    for item in request.tickets:
        # Validate
        if item.confirmed_fault_type not in VALID_FAULT_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid fault_type: '{item.confirmed_fault_type}'")
        if item.confirmed_severity not in VALID_SEVERITIES:
            raise HTTPException(status_code=400, detail=f"Invalid severity: '{item.confirmed_severity}'")

        app = session.get(Application, item.confirmed_app_id)
        if not app:
            raise HTTPException(status_code=404, detail=f"Application {item.confirmed_app_id} not found.")

        ticket_number = _generate_ticket_number(session)
        ticket = Ticket(
            ticket_number=ticket_number,
            intake_id=intake.id,
            primary_application_id=item.confirmed_app_id,
            status="open",
            fault_type=item.confirmed_fault_type,
            severity=item.confirmed_severity,
            complainant_service_no=intake.complainant_service_no,
            complainant_rank=intake.complainant_rank,
            complainant_unit=intake.complainant_unit,
        )
        session.add(ticket)
        session.flush()

        for related_id in item.related_app_ids:
            if related_id != item.confirmed_app_id:
                rel_app = session.get(Application, related_id)
                if rel_app:
                    session.add(TicketRelatedApp(ticket_number=ticket_number, related_application_id=related_id))

        learning_entry = LearningExample(
            ticket_number=ticket_number,
            raw_text=intake.raw_text,
            text_embedding=embedding,
            predicted_app_id=item.predicted_app_id,
            confirmed_app_id=item.confirmed_app_id,
            predicted_fault_type=item.predicted_fault_type,
            confirmed_fault_type=item.confirmed_fault_type,
            predicted_severity=item.predicted_severity,
            confirmed_severity=item.confirmed_severity,
        )
        session.add(learning_entry)

        history = TicketHistory(
            ticket_number=ticket_number,
            changed_by="system",
            old_status="",
            new_status="open",
            notes=f"Ticket created (multi-fault). Routed to {app.owning_team}."
                  + (f" Notes: {item.operator_notes}" if item.operator_notes else ""),
        )
        session.add(history)

        created.append(TicketConfirmResponse(
            ticket_number=ticket_number,
            status="open",
            primary_application_name=app.name,
            fault_type=item.confirmed_fault_type,
            severity=item.confirmed_severity,
            routed_to_team=app.owning_team,
            message=f"Ticket {ticket_number} created.",
        ))

    session.commit()
    return MultiTicketConfirmResponse(
        created_tickets=created,
        message=f"{len(created)} ticket(s) created from intake {request.intake_id}.",
    )

