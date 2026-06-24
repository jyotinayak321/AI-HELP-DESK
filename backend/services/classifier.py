import os
from typing import Optional, List
# pyrefly: ignore [missing-import]
from transformers import pipeline
from sqlmodel import Session, select
from sqlalchemy import text
from models import ClassificationConfig

class TicketClassifier:
    """
    Handles zero-shot categorization for Fault Types (R-11) and Severity Ranks (R-12)
    using a Hybrid Strategy:
      1. History-based k-NN lookup via pgvector.
      2. Database-driven Zero-Shot classification fallback using descriptive prompts.
    """
    
    def __init__(self):
        # Dynamically resolve path to the local model relative to this file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_dir = os.path.join(current_dir, "..", "local_models", "mDeBERTa-v3")
        self.model_path = os.path.normpath(model_dir)
        
        # Initialize zero-shot pipeline strictly from local files (air-gapped)
        self.classifier = pipeline(
            task="zero-shot-classification", 
            model=self.model_path, 
            tokenizer=self.model_path,
            local_files_only=True
        )

    def _get_history_match(self, session: Session, embedding: List[float], category: str) -> Optional[str]:
        """
        Searches learning_examples for a very highly confident past ticket to copy its label.
        Requires a cosine distance < 0.15 (similarity > 85%).
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

    def _fallback_zero_shot(self, session: Session, text_content: str, category: str) -> str:
        """
        Uses the zero-shot model but queries the database for descriptive prompt labels
        to drastically improve accuracy, instead of hardcoding keywords.
        """
        configs = session.exec(select(ClassificationConfig).where(ClassificationConfig.category == category)).all()
        if not configs:
            return "other" if category == "fault_type" else "normal"
            
        # Map descriptions to labels
        desc_to_label = {c.description: c.label for c in configs}
        descriptions = list(desc_to_label.keys())
        
        result = self.classifier(text_content, candidate_labels=descriptions)
        winning_description = result["labels"][0]
        
        return desc_to_label[winning_description]

    def classify_fault_type(self, session: Session, text_content: Optional[str], embedding: List[float]) -> str:
        if text_content is None or not text_content.strip():
            return "other"
        
        # 1. Try history
        history_match = self._get_history_match(session, embedding, "fault_type")
        if history_match:
            print(f"[AI] History match found for fault_type: {history_match}")
            return history_match
            
        # 2. Fallback to descriptive zero-shot
        print("[AI] No history match. Falling back to DB zero-shot for fault_type.")
        return self._fallback_zero_shot(session, text_content.strip(), "fault_type")

    def classify_severity(self, session: Session, text_content: Optional[str], embedding: List[float]) -> str:
        if text_content is None or not text_content.strip():
            return "normal"
            
        # Asymmetric Strategy: Severity bypasses history lookup completely.
        # Vector embeddings cluster topically, which is poor for measuring urgency.
        # We rely 100% on the NLI zero-shot classifier for severity.
        print("[AI] Bypassing history for severity. Using pure DB zero-shot.")
        return self._fallback_zero_shot(session, text_content.strip(), "severity")
