import os
from typing import Optional
from sqlalchemy import text as sqltext


class TicketClassifier:

    def __init__(self):
        pass

    def _get_history_match(self, session, embedding, category):
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"
        query = sqltext("""
            SELECT confirmed_fault_type, confirmed_severity,
                   (text_embedding <=> :embedding) AS distance
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

    def _keyword_classify_fault(self, text):
        text = text.lower()
        if any(w in text for w in ["login", "password", "access", "sign in", "auth"]):
            return "login/access"
        elif any(w in text for w in ["slow", "hang", "freeze", "crash", "not responding"]):
            return "performance/slow"
        elif any(w in text for w in ["error", "failed", "not working", "broken"]):
            return "data error"
        elif any(w in text for w in ["down", "outage", "not available"]):
            return "total outage"
        elif any(w in text for w in ["network", "internet", "connection", "vpn"]):
            return "partial/degraded"
        else:
            return "other"

    def _keyword_classify_severity(self, text):
        text = text.lower()
        if any(w in text for w in ["urgent", "critical", "down", "all users", "cannot work"]):
            return "critical"
        elif any(w in text for w in ["important", "many users", "affecting"]):
            return "high"
        elif any(w in text for w in ["slow", "sometimes", "intermittent"]):
            return "normal"
        else:
            return "low"

    def classify_fault_type(self, session, text_content, embedding):
        if text_content is None or not text_content.strip():
            return "other"
        history_match = self._get_history_match(session, embedding, "fault_type")
        if history_match:
            print(f"[AI] History match: {history_match}")
            return history_match
        return self._keyword_classify_fault(text_content)

    def classify_severity(self, session, text_content, embedding):
        if text_content is None or not text_content.strip():
            return "normal"
        return self._keyword_classify_severity(text_content)