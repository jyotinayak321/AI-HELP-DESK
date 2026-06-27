from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text

class ApplicationSearchEngine:

    def search_candidates(self, db_session: Session, text_embedding: List[float], top_k: int = 5) -> List[Dict]:
        if not text_embedding or all(v == 0.0 for v in text_embedding):
            return []

        embedding_str = "[" + ",".join(str(x) for x in text_embedding) + "]"
        
        query_learning = text("""
            SELECT confirmed_app_id AS app_id, (text_embedding <=> :embedding) AS distance 
            FROM learning_examples 
            WHERE confirmed_app_id IS NOT NULL
            ORDER BY distance ASC LIMIT :limit
        """)
        
        query_symptoms = text("""
            SELECT application_id AS app_id, (embedding <=> :embedding) AS distance 
            FROM application_symptoms 
            ORDER BY distance ASC LIMIT :limit
        """)
        
        query_purposes = text("""
            SELECT application_id AS app_id, (embedding <=> :embedding) AS distance 
            FROM application_purposes 
            ORDER BY distance ASC LIMIT :limit
        """)

        params = {"embedding": embedding_str, "limit": top_k}
        
        res_learning = db_session.execute(query_learning, params).fetchall()
        res_symptoms = db_session.execute(query_symptoms, params).fetchall()
        res_purposes = db_session.execute(query_purposes, params).fetchall()

        candidate_scores = {}
        
        def process_results(results):
            for row in results:
                app_id = getattr(row, 'app_id', None) or getattr(row, 'application_id', None)
                distance = getattr(row, 'distance', None)
                if app_id is None or distance is None:
                    continue
                similarity = 1.0 - float(distance)
                if app_id not in candidate_scores or similarity > candidate_scores[app_id]:
                    candidate_scores[app_id] = similarity

        process_results(res_learning)
        process_results(res_symptoms)
        process_results(res_purposes)

        final_list = [
            {"application_id": app_id, "score": score} 
            for app_id, score in candidate_scores.items()
        ]
        
        final_list.sort(key=lambda x: x["score"], reverse=True)

        return final_list[:top_k]