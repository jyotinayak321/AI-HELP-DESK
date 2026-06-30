import os
from typing import Optional, List
from sqlmodel import Session, select
from sqlalchemy import text
from models import ClassificationConfig
from services.llm_client import predict_fault_and_severity

class TicketClassifier:
    """
    Handles zero-shot categorization for Fault Types (R-11) and Severity Ranks (R-12)
    using a Hybrid Strategy:
      1. History-based k-NN lookup via pgvector (preserved — critical for learning loop).
      2. LLM-based classification fallback via the air-gapped vLLM server (Gemma 4).
         (Replaces the old mDeBERTa-v3 zero-shot pipeline.)
    """

    def __init__(self):
        # No local model to load anymore. The LLM client is used for fallback.
        pass

    def _get_history_match(self, session: Session, embedding: List[float], category: str) -> Optional[str]:
        """
        Searches learning_examples for a very highly confident past ticket to copy its label.
        Requires a cosine distance < 0.08 (similarity > 92%).
        This is the core of the learning loop and must be preserved.
        """
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        query = text("""
            SELECT confirmed_fault_type, confirmed_severity, (text_embedding <=> :embedding) AS distance 
            FROM learning_examples 
            ORDER BY distance ASC LIMIT 1
        """)
        
        result = session.execute(query, {"embedding": embedding_str}).first()
        if result and result.distance is not None and float(result.distance) < 0.08:
            if category == "fault_type" and result.confirmed_fault_type:
                return result.confirmed_fault_type
            elif category == "severity" and result.confirmed_severity:
                return result.confirmed_severity
        return None

    def classify_fault_type(self, session: Session, text_content: Optional[str], embedding: List[float]) -> str:
        """
        Hybrid classification for fault_type:
          1. First, check the learning_examples database for a historical match.
          2. If none, call the LLM (Gemma 4 via vLLM) to classify.
        """
        if text_content is None or not text_content.strip():
            return "other"
        
        # 1. Try history match first (preserves the learning loop)
        history_match = self._get_history_match(session, embedding, "fault_type")
        if history_match:
            print(f"[AI] History match found for fault_type: {history_match}")
            return history_match
            
        # 2. Fallback to LLM classification
        print("[AI] No history match. Calling LLM for fault_type classification.")
        result = predict_fault_and_severity(text_content.strip())
        return result.get("fault_type", "other")

    def classify_severity(self, session: Session, text_content: Optional[str], embedding: List[float]) -> str:
        """
        LLM-based classification for severity.
        History matching is skipped for severity because vector embeddings cluster
        topically (by subject matter), not by urgency, making them a poor signal.
        """
        if text_content is None or not text_content.strip():
            return "normal"
            
        # Always use LLM for severity (no history check — consistent with old strategy)
        print("[AI] Calling LLM for severity classification.")
        result = predict_fault_and_severity(text_content.strip())
        return result.get("severity", "normal")
