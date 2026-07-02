import os
from typing import List, Optional
from sentence_transformers import SentenceTransformer


class TextEmbedder:
    _shared_model = None

    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        model_dir = os.path.join(current_dir, "..", "local_models", "multilingual-e5-base")
        self.model_path = os.path.normpath(model_dir)

    @property
    def model(self):
        if TextEmbedder._shared_model is None:
            print(f"[embedder] Loading model from {self.model_path} (first use)...")
            TextEmbedder._shared_model = SentenceTransformer(self.model_path)
        return TextEmbedder._shared_model

    def get_embedding(self, text: Optional[str]) -> List[float]:
        if text is None:
            return [0.0] * 768

        cleaned_text = text.strip()
        if not cleaned_text:
            return [0.0] * 768

        formatted_text = f"query: {cleaned_text}"
        embedding = self.model.encode(formatted_text)
        return embedding.tolist()
