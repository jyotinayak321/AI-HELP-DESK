from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):

    # -- Database ----------------------------
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/helpdesk_db"

    # -- Server ------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # -- App Info ----------------------------
    APP_NAME: str = "AI Help Desk"
    VERSION: str = "1.0.0"

    # -- AI Models (Air-gapped local paths) --
    MODEL_PATH: str = "./local_models/multilingual-e5-base"
    OLLAMA_URL: str = "http://localhost:11434"

    # -- Offline Mode (HuggingFace) ----------
    TRANSFORMERS_OFFLINE: str = "1"
    HF_HUB_OFFLINE: str = "1"

    # -- Auth (Keycloak) ---------------------
    # Set to True to enforce JWT tokens on all routes.
    # Keep False during development if Keycloak is not running.
    AUTH_ENABLED: bool = True
    KEYCLOAK_URL: str = "http://localhost:8080"
    KEYCLOAK_REALM: str = "ai-helpdesk"
    KEYCLOAK_CLIENT_ID: str = "helpdesk-frontend"

    # -- Phase 2: Voice Layer ----------------
    # STT (Speech-to-Text) — faster-whisper
    STT_MODEL_SIZE: str = "medium"
    STT_DEVICE: str = "auto"          # "auto", "cuda", "cpu"
    STT_COMPUTE_TYPE: str = "default" # "default", "float16", "int8", "float32"

    # TTS (Text-to-Speech)
    TTS_BACKEND: str = "auto"          # "piper", "sapi5", "auto"

    # Voice session
    VOICE_SESSION_TTL: int = 1800      # seconds (30 min default)
    VOICE_MAX_SVC_RETRIES: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
