from pathlib import Path
from typing import List
from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Base Storage Path (outside frontend public root, anchored to backend folder)
    STORAGE_DIR: str = str(BACKEND_DIR / "storage")
    MAX_UPLOAD_SIZE_MB: int = 25
    MAX_PAGE_LIMIT: int = 100
    FILE_RETENTION_DAYS: int = 30

    # AI Provider: 'deterministic', 'gemini', 'openai', 'ollama'
    AI_PROVIDER: str = "deterministic"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"

    SECRET_KEY: str = "local-secret-key-antigravity"
    API_KEY: str = "" # Master API key for remote / production authentication
    REQUIRE_AUTH: bool = False # If True, requires valid API_KEY for all API access
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,https://ai-document-reuse.mokulakshithreddy.workers.dev"

    # Database anchored to backend directory
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'document_reuse.db'}"

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    @model_validator(mode="after")
    def validate_production_security(self):
        if self.ENVIRONMENT.lower() == "production":
            # In production, require strong, non-default SECRET_KEY
            if not self.SECRET_KEY or self.SECRET_KEY == "local-secret-key-antigravity" or len(self.SECRET_KEY) < 32:
                raise ValueError(
                    "CRITICAL SECURITY: In production mode (ENVIRONMENT='production'), "
                    "a cryptographically secure SECRET_KEY of at least 32 characters must be configured."
                )
            # If REQUIRE_AUTH is active in production, ensure API_KEY is set
            if self.REQUIRE_AUTH and (not self.API_KEY or len(self.API_KEY) < 16):
                raise ValueError(
                    "CRITICAL SECURITY: REQUIRE_AUTH is enabled, but API_KEY is missing or too short (must be >= 16 chars)."
                )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def allowed_origins_list(self) -> List[str]:
        origins = []
        for o in self.ALLOWED_ORIGINS.split(","):
            cleaned = o.strip().rstrip("/")
            if cleaned and cleaned not in origins:
                origins.append(cleaned)
        return origins

    @property
    def base_storage_path(self) -> Path:
        p = Path(self.STORAGE_DIR).resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def originals_path(self) -> Path:
        p = self.base_storage_path / "originals"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def working_path(self) -> Path:
        p = self.base_storage_path / "working"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def generated_path(self) -> Path:
        p = self.base_storage_path / "generated"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def temp_path(self) -> Path:
        p = self.base_storage_path / "temp"
        p.mkdir(parents=True, exist_ok=True)
        return p

settings = Settings()
