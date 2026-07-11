"""
services/pipeline.py — Shared AI Pipeline Orchestrator
======================================================
Executes the standard sequence of AI classifications and searches
for a given complaint text. Shared by both REST and Voice pathways.
"""

from sqlmodel import Session
from sqlalchemy import text
from typing import List, Dict, Any, Tuple
import datetime as dt_lib
from datetime import timezone, timedelta

from models import Application
from services.embedder import TextEmbedder
from services.classifier import TicketClassifier
from services.search import ApplicationSearchEngine
from services.dependencies import ApplicationDependencyEngine

_embedder = None
_classifier = None
_search_engine = None
_dependency_engine = None

def _get_services():
    global _embedder, _classifier, _search_engine, _dependency_engine
    if _embedder is None:
        _embedder = TextEmbedder()
        _classifier = TicketClassifier()
        _search_engine = ApplicationSearchEngine()
        _dependency_engine = ApplicationDependencyEngine()
    return _embedder, _classifier, _search_engine, _dependency_engine


def run_ai_pipeline(
    session: Session,
    complaint_text: str,
    complainant_service_no: str,
) -> Tuple[str, str, List[Dict[str, Any]], List[Dict[str, Any]], bool]:
    """
    Executes the shared AI logic to classify a complaint and find related context.
    
    Returns:
        fault_type: str
        severity: str
        candidates: List[dict] (keys: application_id, application_name, confidence_score, is_primary, expansion_reason)
        potential_duplicates: List[dict] (keys: ticket_number, complainant_service_no, text_snippet, status, is_same_user)
        is_repeat_caller: bool
    """
    embedder, classifier, search_engine, dependency_engine = _get_services()

    # Step 1: Generate embedding
    embedding = embedder.get_embedding(complaint_text)

    # Step 2: Semantic Duplicate & Mass Outage Check
    embedding_str = "[" + ",".join(map(str, embedding)) + "]"
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
        is_same = (row.complainant_service_no == complainant_service_no)
        dist = float(row.distance)
        
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

    # Step 3: Classify fault type and severity
    fault_type = classifier.classify_fault_type(session, complaint_text, embedding)
    severity = classifier.classify_severity(session, complaint_text, embedding)

    # Step 4: Find candidate applications via vector similarity
    raw_candidates = search_engine.search_candidates(session, embedding)
    
    enriched_candidates = []
    for cand in raw_candidates:
        app_obj = session.get(Application, cand["application_id"])
        if app_obj:
            enriched_candidates.append({
                "application_id": app_obj.id,
                "application_name": app_obj.name,
                "confidence_score": cand["score"],
                "is_primary": (len(enriched_candidates) == 0),
                "expansion_reason": None,
            })

    # Step 5: Expand dependencies
    primary_candidate = enriched_candidates[0] if enriched_candidates else None
    if primary_candidate:
        dep_ids = dependency_engine.expand_dependencies(
            db_session=session,
            primary_app_id=primary_candidate["application_id"],
            fault_type=fault_type,
        )
        existing_ids = {c["application_id"] for c in enriched_candidates}
        for d_id in dep_ids:
            if d_id not in existing_ids:
                d_app = session.get(Application, d_id)
                if d_app:
                    enriched_candidates.append({
                        "application_id": d_id,
                        "application_name": d_app.name,
                        "confidence_score": 0.0,
                        "is_primary": False,
                        "expansion_reason": f"Cascade from {fault_type}",
                    })

    return fault_type, severity, enriched_candidates, potential_duplicates, is_repeat
