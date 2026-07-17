from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):

    # -- Database ----------------------------
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/helpdesk_db"

    # -- Server ------------------------------
    HOST: str = "0.0.0.0"
    PORT: int = 8001
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
    STT_KEEP_MODEL_LOADED: bool = False    #True  = keep in memory (offline GPU PC, faster response)
    
    
    # VAD (Voice Activity Detection) — Silero VAD
    VAD_DEVICE: str = "cpu"           # ✅ NEW: "cpu" on home PC, "cuda" on offline GPU PC


    
    # TTS (Text-to-Speech)
    TTS_BACKEND: str = "auto"          # "piper", "sapi5", "auto"

    # Voice session
    VOICE_SESSION_TTL: int = 1800      # seconds (30 min default)
    VOICE_MAX_SVC_RETRIES: int = 3

    # -- Phase 4: LiveKit Media Transport (runtime backend flag) -----
    # Set LIVEKIT_ENABLED=true to activate real-time WebRTC media transport.
    # When false (default), the existing record/upload REST audio path
    # remains the only path. The frontend reads this flag from the
    # /voice/start response (no build-time env var) and decides whether
    # to join a LiveKit room or use the legacy path.
    LIVEKIT_ENABLED: bool = False
    LIVEKIT_URL: str = "ws://localhost:7880"
    LIVEKIT_API_KEY: str = "helpdesk_key"
    LIVEKIT_API_SECRET: str = "helpdesk_secret_change_in_production"
    # Identity used by the AI agent when joining a room as a participant.
    LIVEKIT_AGENT_IDENTITY: str = "ai-helpdesk-agent"
    # STT concurrency: single lock protects the shared SpeechToTextEngine.
    # Future: increase to allow a pool when concurrency becomes a bottleneck.
    LIVEKIT_STT_POOL_SIZE: int = 1

    # -- Phase 3: LLM Guardrail & Classification ----
    # The vLLM server URL exposed by the air-gapped environment.
    # Example: "http://10.0.0.5:8001/v1"
    VLLM_API_URL: str = "http://localhost:8010/v1"
    # The model name as registered on the vLLM server.
    VLLM_MODEL_NAME: str = "google/gemma-4-31B-it"
    # API key if the vLLM server requires one (leave blank if not needed).
    VLLM_API_KEY: str = "none"
    # --- OFFLINE DEVELOPMENT FLAG ---
    # Set to True at home to skip LLM network calls entirely.
    # The system will return a realistic mock response so the UI can be built
    # and tested without needing access to the air-gapped vLLM server.
    MOCK_LLM: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
