from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import GenerationJob, GeneratedDocument, Template
from app.schemas.api_schemas import GenerationJobResponse, ValidationReport
from app.core.errors import AppException, AppErrorCode
from app.core.logging import log_event

router = APIRouter(prefix="/generations", tags=["Generations"])

@router.get("", response_model=List[GenerationJobResponse])
def list_generations(limit: int = 20, db: Session = Depends(get_db)):
    jobs = db.query(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(limit).all()
    results = []
    for j in jobs:
        val_rep = ValidationReport(**j.validation_report) if j.validation_report else None
        results.append(
            GenerationJobResponse(
                id=j.id,
                template_id=j.template_id,
                template_version=j.template_version,
                status=j.status,
                created_at=j.created_at,
                error_code=j.error_code,
                error_message=j.error_message,
                validation_report=val_rep,
                download_url=f"/api/v1/generations/{j.id}/download" if j.status == "completed" else None
            )
        )
    return results

@router.get("/{id}", response_model=GenerationJobResponse)
def get_generation_job(id: str, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).filter(GenerationJob.id == id).first()
    if not job:
        raise AppException(code=AppErrorCode.JOB_NOT_FOUND, message="Generation job not found", status_code=status.HTTP_404_NOT_FOUND)

    val_rep = ValidationReport(**job.validation_report) if job.validation_report else None
    return GenerationJobResponse(
        id=job.id,
        template_id=job.template_id,
        template_version=job.template_version,
        status=job.status,
        created_at=job.created_at,
        error_code=job.error_code,
        error_message=job.error_message,
        validation_report=val_rep,
        download_url=f"/api/v1/generations/{job.id}/download" if job.status == "completed" else None
    )

@router.get("/{id}/download")
def download_generated_artifact(id: str, db: Session = Depends(get_db)):
    job = db.query(GenerationJob).filter(GenerationJob.id == id).first()
    if not job:
        raise AppException(code=AppErrorCode.JOB_NOT_FOUND, message="Generation job not found", status_code=status.HTTP_404_NOT_FOUND)

    if job.status != "completed":
        raise AppException(
            code=AppErrorCode.GENERATION_VALIDATION_FAILED,
            message="Cannot download artifact from an uncompleted or failed generation job."
        )

    gen_doc = job.generated_document
    if not gen_doc:
        raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message="Generated document file record not found")

    file_path = Path(gen_doc.storage_path)
    if not file_path.exists():
        raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message="Generated file missing on disk")

    template = job.template
    base_name = template.name.replace(" ", "_") if template else "generated_document"
    download_filename = f"{base_name}_{job.id[:8]}.{gen_doc.format}"

    media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if gen_doc.format == "docx" else "application/pdf"

    log_event("ARTIFACT_DOWNLOADED", job.id)
    return FileResponse(
        path=str(file_path),
        filename=download_filename,
        media_type=media_type
    )
