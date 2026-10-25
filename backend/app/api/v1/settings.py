from fastapi import APIRouter
from app.core.config import settings
from app.schemas.api_schemas import AppSettingsDTO, UpdateSettingsRequest

router = APIRouter(prefix="/settings", tags=["Settings"])

@router.get("", response_model=AppSettingsDTO)
def get_settings():
    return AppSettingsDTO(
        ai_provider=settings.AI_PROVIDER,
        has_gemini_key=bool(settings.GEMINI_API_KEY),
        has_openai_key=bool(settings.OPENAI_API_KEY),
        max_upload_size_mb=settings.MAX_UPLOAD_SIZE_MB,
        max_page_limit=settings.MAX_PAGE_LIMIT,
        file_retention_days=settings.FILE_RETENTION_DAYS,
        storage_dir=str(settings.base_storage_path)
    )

@router.post("", response_model=AppSettingsDTO)
def update_settings(req: UpdateSettingsRequest):
    if req.ai_provider is not None:
        settings.AI_PROVIDER = req.ai_provider
    if req.gemini_api_key is not None:
        settings.GEMINI_API_KEY = req.gemini_api_key
    if req.openai_api_key is not None:
        settings.OPENAI_API_KEY = req.openai_api_key
    if req.file_retention_days is not None:
        settings.FILE_RETENTION_DAYS = req.file_retention_days

    return get_settings()
