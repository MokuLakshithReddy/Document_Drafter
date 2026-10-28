from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.errors import AppException
from app.core.logging import logger
from app.db.session import engine, Base, run_migrations
import app.models # register all models

from app.api.v1.documents import router as documents_router
from app.api.v1.analysis import router as analysis_router
from app.api.v1.templates import router as templates_router
from app.api.v1.generations import router as generations_router
from app.api.v1.settings import router as settings_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    run_migrations()
    logger.info(f"Storage directory: {settings.base_storage_path}")

    # Security audit notifications on startup
    if settings.SECRET_KEY == "local-secret-key-antigravity":
        logger.warning(
            "SECURITY NOTICE: Using default development SECRET_KEY. "
            "For production deployments, set a random 32+ character SECRET_KEY in your environment."
        )

    if settings.REQUIRE_AUTH or settings.API_KEY:
        logger.info("SECURITY: API Authentication is ENABLED (API Key required).")
    else:
        logger.info("SECURITY: Running in Local-First Development Mode (no API key enforced).")

    logger.info("AI Document Reuse Platform initialized successfully.")
    yield

app = FastAPI(
    title="AI Document Reuse Platform API",
    description="Private, local-first API for deterministic and AI-assisted document reuse.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration strictly bound to explicit allowlist (no wildcard origin regex)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Custom exception handler for structured AppException
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.detail
    )

# General HTTP exception handler
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled server exception")
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected server error occurred."
        }
    )

# Include Routers
app.include_router(documents_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(templates_router, prefix="/api/v1")
app.include_router(generations_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")

@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "service": "AI Document Reuse Platform",
        "version": "1.0.0",
        "ai_provider": settings.AI_PROVIDER
    }
