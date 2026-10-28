from pathlib import Path
from typing import Dict
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import Document, AuditEvent
from app.schemas.api_schemas import AnalysisResultDTO
from app.services.extraction.docx_extractor import DocxExtractor
from app.services.extraction.pdf_extractor import PdfExtractor
from app.services.analysis.candidate_detector import CandidateDetector
from app.services.analysis.ai_adapter import get_ai_adapter
from app.core.errors import AppException, AppErrorCode
from app.core.logging import log_event
from app.core.auth import get_current_identity
from app.core.config import settings

router = APIRouter(tags=["Analysis"])

# In-memory store for recent analysis results
_analysis_cache: Dict[str, AnalysisResultDTO] = {}

@router.post("/documents/{id}/analyze", response_model=AnalysisResultDTO)
async def analyze_document(
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
            message="Access denied: you do not have permission to analyze this document.",
            status_code=status.HTTP_403_FORBIDDEN
        )

    file_path = Path(doc.storage_path)
    if not file_path.exists():
        raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message="Document file missing on disk")

    # 1. Structural extraction
    if doc.format == "docx":
        extracted = DocxExtractor.extract(file_path, doc.id)
    else:
        extracted = PdfExtractor.extract(file_path, doc.id)

    # 2. Deterministic candidate detection
    occurrences, base_variables = CandidateDetector.detect(extracted)

    # 3. AI enhancement behind provider adapter
    adapter = get_ai_adapter()
    result = await adapter.analyze(extracted, occurrences, base_variables)

    # Persist in-memory cache and in SQLite database
    _analysis_cache[id] = result
    doc.analysis_json = result.model_dump(mode="json")

    # Update document status
    doc.status = "analyzed"
    audit = AuditEvent(event_type="DOCUMENT_ANALYZED", resource_id=id)
    db.add(audit)
    db.commit()

    log_event("DOCUMENT_ANALYZED", id)
    return result

@router.get("/analysis/{id}", response_model=AnalysisResultDTO)
async def get_analysis_result(
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
            message="Access denied: you do not have permission to access analysis for this document.",
            status_code=status.HTTP_403_FORBIDDEN
        )

    if id in _analysis_cache:
        return _analysis_cache[id]

    if doc.analysis_json:
        result = AnalysisResultDTO(**doc.analysis_json)
        _analysis_cache[id] = result
        return result
    
    # If not previously analyzed or cached, run analysis
    return await analyze_document(id, identity, db)
