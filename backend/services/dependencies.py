from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

class ApplicationDependencyEngine:
    """
    Handles conditional dependency expansion to traverse infrastructure graphs
    while filtering out noisy/irrelevant alerts based on the AI's predicted fault type.
    Satisfies Requirement R-10, entirely driven dynamically from the database (R-3).
    """

    def expand_dependencies(self, db_session: Session, primary_app_id: Optional[int], fault_type: str) -> List[int]:
        """
        Conditionally queries the application_dependencies graph table to find underlying root causes
        by exactly matching the predicted fault_type with the configured dependency_nature.
        """
        # Edge Case Protection: Invalid application IDs or empty fault types
        if not primary_app_id or not fault_type:
            return []

        clean_fault_type = fault_type.strip()
        if not clean_fault_type:
            return []

        # Raw query blindly traversing the DB without hardcoded dictionaries
        query = text("""
            SELECT dependent_app_id
            FROM application_dependencies
            WHERE source_app_id = :app_id
            AND dependency_nature = :fault_type
        """)

        # Execute query against the session
        results = db_session.execute(query, {"app_id": primary_app_id, "fault_type": clean_fault_type}).fetchall()

        # Extract and return a unique list of dependent application IDs
        dependent_ids = list(set(row.dependent_app_id for row in results if row.dependent_app_id is not None))

        return dependent_ids
