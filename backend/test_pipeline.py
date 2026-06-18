#!backend/venv/Scripts/python.exe
import os
import sys

# Ensure backend directory is in the path to resolve imports correctly across OS environments
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.embedder import TextEmbedder
from services.classifier import TicketClassifier
from services.search import ApplicationSearchEngine
from services.dependencies import ApplicationDependencyEngine

class MockRow:
    """Simulates SQLAlchemy dynamic row attribute access."""
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

class MockDatabaseSession:
    """
    Safely intercepts SQLAlchemy execute calls in memory to prevent actual database connections.
    Provides targeted mock rows matching our master PostgreSQL schema layout.
    """
    def execute(self, query, params=None):
        query_str = str(query).lower()
        
        class MockResult:
            def __init__(self, rows):
                self.rows = rows
            def fetchall(self):
                return self.rows

        # 1. Search Query Intercepts
        if "application_symptoms" in query_str:
            # Simulate a match for Application ID 4.
            # search.py uses: score = 1.0 - distance. For a target score of 0.89, distance must be 0.11.
            return MockResult([MockRow(application_id=4, distance=0.11)])
            
        elif "application_purposes" in query_str or "learning_examples" in query_str:
            # Return empty to isolate our mock test signal
            return MockResult([])
            
        # 2. Dependency Graph Intercept
        elif "application_dependencies" in query_str:
            # Simulate a cascading dependency to Application ID 12
            if params and params.get("app_id") == 4:
                return MockResult([MockRow(dependent_app_id=12)])
            return MockResult([])
            
        return MockResult([])

def run_test():
    print("🚀 Initializing AI Pipeline Components (Loading Local Air-Gapped Models)...")
    embedder = TextEmbedder()
    classifier = TicketClassifier()
    search_engine = ApplicationSearchEngine()
    dependency_engine = ApplicationDependencyEngine()
    
    mock_db = MockDatabaseSession()
    
    test_text = "Yaar portal load nahi ho raha backend pe, login block ho gaya aur OTP bhi nahi aa raha validation ka"
    
    print("\n[1] Executing Zero-Shot Classification...")
    fault_type = classifier.classify_fault_type(test_text)
    severity = classifier.classify_severity(test_text)
    
    print("[2] Generating Multilingual Text Embeddings...")
    vector = embedder.get_embedding(test_text)
    vector_sample = str(vector[:3]) + "... (768 dimensions)"
    
    print("[3] Querying Vector Database for Application Match (Mocked)...")
    candidates = search_engine.search_candidates(mock_db, vector)
    primary_app = candidates[0] if candidates else None
    
    print("[4] Traversing Conditional Dependency Graph (Mocked)...")
    dependent_apps = []
    if primary_app:
        dependent_apps = dependency_engine.expand_dependencies(mock_db, primary_app["application_id"], fault_type)
        
    print("\n==================================================")
    print("🎯 INTELLIGENT HELP DESK PIPELINE SUMMARY")
    print("==================================================")
    print(f"📄 Raw Input Text : {test_text}")
    print(f"🏷️  Extracted Tags : [Fault: {fault_type.upper()}] | [Severity: {severity.upper()}]")
    print(f"🧠 Vector Extract : {vector_sample}")
    
    if primary_app:
        print(f"🎯 Primary App Hit: App ID {primary_app['application_id']} (Confidence Score: {primary_app['score']:.2f})")
    else:
        print("🎯 Primary App Hit: NONE")
        
    if dependent_apps:
        print(f"🔗 Hidden Cascades: Suspected Root Causes at App IDs {dependent_apps}")
    else:
        print("🔗 Hidden Cascades: None required for this fault type.")
    print("==================================================")

if __name__ == "__main__":
    run_test()
