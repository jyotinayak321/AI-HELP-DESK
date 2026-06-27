import os
from typing import List, Optional
from sentence_transformers import SentenceTransformer

class TextEmbedder:
    """
    Handles feature extraction for the Intelligent IT Help Desk system,
    providing language-agnostic embeddings (English, Hindi, Hinglish).
    """
    def __init__(self):
        # Dynamically resolve path to the local model relative to this file's location
        # This file is in backend/services/
        # Model is in backend/local_models/multilingual-e5-base
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_dir = r"D:\ai_models\multilingual-e5-base"
        self.model_path = os.path.normpath(model_dir)
        
        # Load model strictly from local storage (air-gapped)
        self.model = SentenceTransformer(self.model_path)

    def get_embedding(self, text: Optional[str]) -> List[float]:
        # Handle edge cases gracefully to avoid model crashes
        if text is None:
            return [0.0] * 768
            
        cleaned_text = text.strip()
        if not cleaned_text:
            return [0.0] * 768
            
        # E5 requires the "query: " prefix for asymmetric retrieval tasks
        formatted_text = f"query: {cleaned_text}"
        
        # Extract features
        embedding = self.model.encode(formatted_text)
        
        # Ensure primitive type compatibility with SQLModel and pgvector
        return embedding.tolist()
