from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import text

class ApplicationSearchEngine:
    """
    Semantic search engine connecting text embeddings to application knowledge graphs.
    Satisfies R-9 (Ranked candidates list) and R-24 (Retrieval-based learning).
    """

    def search_candidates(self, db_session: Session, text_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """
        Executes a multi-layer vector search across symptoms, purposes, and learning examples.
        """
        # Edge Case Protection: Bypass mathematically unstable embeddings
        if not text_embedding or all(v == 0.0 for v in text_embedding):
            return []

        # Convert the float list into a pgvector compatible string format
        embedding_str = "[" + ",".join(str(x) for x in text_embedding) + "]"
        
        # 1. Search Historical Learning Feedback (R-24)
        query_learning = text("""
            SELECT confirmed_app_id AS app_id, (text_embedding <=> :embedding) AS distance 
            FROM learning_examples 
            WHERE confirmed_app_id IS NOT NULL
            ORDER BY distance ASC LIMIT :limit
        """)
        
        # 2. Search Explicit Symptom Definitions
        query_symptoms = text("""
            SELECT application_id AS app_id, (embedding <=> :embedding) AS distance 
            FROM application_symptoms 
            ORDER BY distance ASC LIMIT :limit
        """)
        
        # 3. Search Application Business Purposes
        query_purposes = text("""
            SELECT application_id AS app_id, (embedding <=> :embedding) AS distance 
            FROM application_purposes 
            ORDER BY distance ASC LIMIT :limit
        """)

        params = {"embedding": embedding_str, "limit": top_k}
        
        # Execute queries against the database session
        res_learning = db_session.execute(query_learning, params).fetchall()
        res_symptoms = db_session.execute(query_symptoms, params).fetchall()
        res_purposes = db_session.execute(query_purposes, params).fetchall()

        # Aggregation Dictionary to track best score per app_id
        candidate_scores = {}

        def process_results(results):
            for row in results:
                if row.app_id is None or row.distance is None:
                    continue
                # Convert cosine distance to similarity score (clamped to 0.0 - 1.0)
                similarity = max(0.0, min(1.0, 1.0 - float(row.distance)))
                
                # Merge logic: Take highest similarity score found across all tables
                if row.app_id not in candidate_scores or similarity > candidate_scores[row.app_id]:
                    candidate_scores[row.app_id] = similarity

        # Process all three distinct vector sources
        process_results(res_learning)
        process_results(res_symptoms)
        process_results(res_purposes)

        # Build final sorted candidate list
        final_list = [
            {"application_id": app_id, "score": score} 
            for app_id, score in candidate_scores.items()
        ]
        
        # Sort descending (highest similarity first)
        final_list.sort(key=lambda x: x["score"], reverse=True)

        return final_list[:top_k]
