from fastapi import APIRouter, UploadFile, File, Depends, status
from sqlalchemy.orm import Session
from pathlib import Path
from app.db.session import get_db
from app.models.entities import Document, AuditEvent
from app.schemas.api_schemas import DocumentCreateResponse, DocumentDetailResponse
from app.services.storage.storage_manager import StorageManager
from app.core.errors import AppException, AppErrorCode
from app.core.logging import log_event
from app.core.auth import get_current_identity
from app.core.config import settings

router = APIRouter(prefix="/documents", tags=["Documents"])

@router.post("", response_model=DocumentCreateResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    identity: str = Depends(get_current_identity),
    db: Session = Depends(get_db)
):
    content = await file.read()
    filename = file.filename or "uploaded_document"

    doc_id, fmt, sha256, stored_path, page_count = StorageManager.save_upload(filename, content)

    doc = Document(
        id=doc_id,
        filename=filename,
        format=fmt,
        sha256=sha256,
        storage_path=str(stored_path),
        page_count=page_count,
        status="uploaded",
        owner_id=identity
    )
    db.add(doc)
    audit = AuditEvent(event_type="DOCUMENT_UPLOADED", resource_id=doc_id)
    db.add(audit)
    db.commit()
    db.refresh(doc)

    log_event("DOCUMENT_UPLOADED", doc_id)
    return DocumentCreateResponse(
        id=doc.id,
        filename=doc.filename,
        format=doc.format,
        sha256=doc.sha256,
        created_at=doc.created_at,
        status=doc.status,
        page_count=doc.page_count
    )

@router.get("/{id}", response_model=DocumentDetailResponse)
def get_document(
    id: str,
    identity: str = Depends(get_current_identity),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message="Document not found", status_code=status.HTTP_404_NOT_FOUND)

    # Ownership check
    if (settings.REQUIRE_AUTH or (identity != "default" and doc.owner_id != "default")) and doc.owner_id != identity:
        raise AppException(
            code=AppErrorCode.FORBIDDEN,
            message="Access denied: you do not have permission to access this document.",
            status_code=status.HTTP_403_FORBIDDEN
        )
    
    return DocumentDetailResponse(
        id=doc.id,
        filename=doc.filename,
        format=doc.format,
        sha256=doc.sha256,
        created_at=doc.created_at,
        status=doc.status,
        page_count=doc.page_count,
        error_message=doc.error_message
    )

@router.delete("/{id}", status_code=status.HTTP_200_OK)
def delete_document(
    id: str,
    identity: str = Depends(get_current_identity),
    db: Session = Depends(get_db)
):
    doc = db.query(Document).filter(Document.id == id).first()
    if not doc:
        raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message="Document not found", status_code=status.HTTP_404_NOT_FOUND)

    # Ownership check
    if (settings.REQUIRE_AUTH or (identity != "default" and doc.owner_id != "default")) and doc.owner_id != identity:
        raise AppException(
            code=AppErrorCode.FORBIDDEN,
            message="Access denied: you do not have permission to delete this document.",
            status_code=status.HTTP_403_FORBIDDEN
        )

    # Clean up physical file
    StorageManager.delete_document_files(doc.storage_path)

    # Cascade delete database record (SQLAlchemy cascade deletes templates, variables, jobs)
    db.delete(doc)
    audit = AuditEvent(event_type="DOCUMENT_DELETED", resource_id=id)
    db.add(audit)
    db.commit()

    log_event("DOCUMENT_DELETED", id)
    return {"message": "Document and associated templates/generations deleted successfully", "id": id}
