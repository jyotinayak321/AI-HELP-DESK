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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings():
    return Settings()

settings = get_settings()
