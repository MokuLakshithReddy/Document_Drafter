from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # Base Storage Path (outside frontend public root)
    STORAGE_DIR: str = "./storage"
    MAX_UPLOAD_SIZE_MB: int = 25
    MAX_PAGE_LIMIT: int = 100
    FILE_RETENTION_DAYS: int = 30

    # AI Provider: 'deterministic', 'gemini', 'openai', 'ollama'
    AI_PROVIDER: str = "deterministic"
    GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"

    SECRET_KEY: str = "local-secret-key-antigravity"
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000"

    # Database
    DATABASE_URL: str = "sqlite:///./document_reuse.db"

    model_config = SettingsConfigDict(env_file=".env", extra="allow")

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

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
