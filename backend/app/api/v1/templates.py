from pathlib import Path
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.entities import (
    Document,
    Template,
    TemplateVariable,
    VariableOccurrence,
    GenerationJob,
    GenerationValue,
    GeneratedDocument,
    AuditEvent
)
from app.schemas.api_schemas import (
    SaveTemplateRequest,
    TemplateSummaryDTO,
    TemplateDetailDTO,
    VariableDTO,
    OccurrenceDTO,
    UpdateVariableRequest,
    GenerateDocumentRequest,
    GenerationJobResponse,
    SourceLocator
)
from app.services.storage.storage_manager import StorageManager
from app.services.replacement.docx_replacer import DocxReplacer
from app.services.replacement.pdf_replacer import PdfReplacer
from app.services.validation.post_generator_validator import PostGeneratorValidator
from app.core.errors import AppException, AppErrorCode
from app.core.logging import log_event
from app.core.config import settings

router = APIRouter(prefix="/templates", tags=["Templates"])

import uuid
from app.api.v1.analysis import _analysis_cache

@router.post("", response_model=TemplateDetailDTO, status_code=status.HTTP_201_CREATED)
def save_template(req: SaveTemplateRequest, db: Session = Depends(get_db)):
    doc = db.query(Document).filter(Document.id == req.document_id).first()
    if not doc:
        raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message="Source document not found", status_code=status.HTTP_404_NOT_FOUND)

    template = Template(
        name=req.name,
        source_document_id=doc.id,
        version=1,
        source_checksum=doc.sha256,
        status="active"
    )
    db.add(template)
    db.flush()

    # Save variables and occurrences with unique database IDs
    for v in req.variables:
        var_uid = str(uuid.uuid4())
        tvar = TemplateVariable(
            id=var_uid,
            template_id=template.id,
            client_id=v.id,
            key=v.key,
            label=v.label,
            type=v.type,
            required=v.required,
            status=v.status,
            default_value=v.replacement_value,
            confidence=str(v.confidence) if v.confidence else "1.0",
            description=v.reason
        )
        db.add(tvar)

        # For occurrences, resolve source locator
        for occ_id in v.occurrence_ids:
            occ_uid = str(uuid.uuid4())
            loc = {"container_id": "auto", "kind": "paragraph"}
            if req.occurrences:
                matched_occ = next((o for o in req.occurrences if o.id == occ_id), None)
                if matched_occ:
                    loc = matched_occ.source_locator.model_dump()
            elif doc.id in _analysis_cache:
                matched_occ = next((o for o in _analysis_cache[doc.id].occurrences if o.id == occ_id), None)
                if matched_occ:
                    loc = matched_occ.source_locator.model_dump()

            occ_record = VariableOccurrence(
                id=occ_uid,
                variable_id=tvar.id,
                source_locator=loc,
                original_text=v.original_value,
                status="active"
            )
            db.add(occ_record)

    db.add(AuditEvent(event_type="TEMPLATE_SAVED", resource_id=template.id))
    db.commit()
    db.refresh(template)

    log_event("TEMPLATE_SAVED", template.id)
    return get_template(template.id, db)

@router.get("", response_model=List[TemplateSummaryDTO])
def list_templates(db: Session = Depends(get_db)):
    templates = db.query(Template).filter(Template.status == "active").order_by(Template.created_at.desc()).all()
    summaries = []
    for t in templates:
        summaries.append(
            TemplateSummaryDTO(
                id=t.id,
                name=t.name,
                source_document_id=t.source_document_id,
                source_filename=t.source_document.filename if t.source_document else "Unknown",
                source_format=t.source_document.format if t.source_document else "docx",
                version=t.version,
                status=t.status,
                created_at=t.created_at,
                variable_count=len(t.variables)
            )
        )
    return summaries

@router.get("/{id}", response_model=TemplateDetailDTO)
def get_template(id: str, db: Session = Depends(get_db)):
    t = db.query(Template).filter(Template.id == id).first()
    if not t:
        raise AppException(code=AppErrorCode.TEMPLATE_NOT_FOUND, message="Template not found", status_code=status.HTTP_404_NOT_FOUND)

    var_dtos: List[VariableDTO] = []
    occ_dtos: List[OccurrenceDTO] = []

    for v in t.variables:
        occ_ids = [o.id for o in v.occurrences]
        var_dtos.append(
            VariableDTO(
                id=v.client_id or v.id,
                key=v.key,
                label=v.label,
                type=v.type,
                original_value=v.occurrences[0].original_text if v.occurrences else "",
                replacement_value=v.default_value or "",
                occurrence_ids=occ_ids,
                confidence=float(v.confidence) if v.confidence else 1.0,
                reason=v.description,
                required=v.required,
                status=v.status
            )
        )
        for o in v.occurrences:
            occ_dtos.append(
                OccurrenceDTO(
                    id=o.id,
                    variable_id=v.id,
                    source_locator=SourceLocator(
                        kind=o.source_locator.get("kind", "paragraph"),
                        container_id=o.source_locator.get("container_id", "body/p[0]")
                    ),
                    original_text=o.original_text,
                    status=o.status
                )
            )

    return TemplateDetailDTO(
        id=t.id,
        name=t.name,
        source_document_id=t.source_document_id,
        source_filename=t.source_document.filename if t.source_document else "Unknown",
        source_format=t.source_document.format if t.source_document else "docx",
        source_checksum=t.source_checksum,
        version=t.version,
        status=t.status,
        created_at=t.created_at,
        variables=var_dtos,
        occurrences=occ_dtos
    )

@router.patch("/{id}/variables/{variable_id}", response_model=VariableDTO)
def update_variable(id: str, variable_id: str, req: UpdateVariableRequest, db: Session = Depends(get_db)):
    tvar = db.query(TemplateVariable).filter(TemplateVariable.id == variable_id, TemplateVariable.template_id == id).first()
    if not tvar:
        raise AppException(code=AppErrorCode.INVALID_VALUE, message="Variable not found in template", status_code=status.HTTP_404_NOT_FOUND)

    if req.key is not None:
        tvar.key = req.key
    if req.label is not None:
        tvar.label = req.label
    if req.type is not None:
        tvar.type = req.type
    if req.status is not None:
        tvar.status = req.status
    if req.required is not None:
        tvar.required = req.required
    if req.replacement_value is not None:
        tvar.default_value = req.replacement_value

    db.commit()
    db.refresh(tvar)

    occ_ids = [o.id for o in tvar.occurrences]
    return VariableDTO(
        id=tvar.id,
        key=tvar.key,
        label=tvar.label,
        type=tvar.type,
        original_value=tvar.occurrences[0].original_text if tvar.occurrences else "",
        replacement_value=tvar.default_value or "",
        occurrence_ids=occ_ids,
        confidence=float(tvar.confidence) if tvar.confidence else 1.0,
        reason=tvar.description,
        required=tvar.required,
        status=tvar.status
    )

@router.post("/{id}/generate", response_model=GenerationJobResponse)
def generate_document(id: str, req: GenerateDocumentRequest, db: Session = Depends(get_db)):
    t = db.query(Template).filter(Template.id == id).first()
    if not t:
        raise AppException(code=AppErrorCode.TEMPLATE_NOT_FOUND, message="Template not found", status_code=status.HTTP_404_NOT_FOUND)

    doc = t.source_document
    if not doc:
        raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message="Source document not found")

    original_file_path = Path(doc.storage_path)
    if not original_file_path.exists():
        raise AppException(code=AppErrorCode.DOCUMENT_NOT_FOUND, message="Original source file not found on disk")

    # 1. Source Checksum validation (AT-12)
    current_checksum = StorageManager.compute_sha256(original_file_path)
    if current_checksum != t.source_checksum:
        raise AppException(
            code=AppErrorCode.SOURCE_CHANGED,
            message="Source document has changed since template creation. Please re-analyze the document.",
            details={"template_checksum": t.source_checksum, "current_checksum": current_checksum}
        )

    # 2. Check required variables and build replacement instructions
    approved_replacements: List[Dict[str, Any]] = []
    excluded_texts: List[str] = []

    for var in t.variables:
        # Check if variable is approved or excluded
        if var.status == "excluded":
            for occ in var.occurrences:
                excluded_texts.append(occ.original_text)
            continue

        # Look for value provided by key or by id or client_id
        val = req.values.get(var.id) or (req.values.get(var.client_id) if var.client_id else None) or req.values.get(var.key) or var.default_value or ""
        if var.required and not val.strip():
            raise AppException(
                code=AppErrorCode.INVALID_VALUE,
                message=f"Missing required value for variable '{var.label}' ({var.key})",
                details={"variable_key": var.key}
            )

        if not val.strip():
            # Leave original value unchanged
            continue

        # Build replacement entries for each occurrence
        for occ in var.occurrences:
            if occ.status == "active":
                approved_replacements.append({
                    "occurrence_id": occ.id,
                    "container_id": occ.source_locator.get("container_id", "body/p[0]") if occ.source_locator else "body/p[0]",
                    "original_text": occ.original_text,
                    "new_text": val,
                    "page": occ.source_locator.get("page") if occ.source_locator else None,
                    "bbox": occ.source_locator.get("bbox") if occ.source_locator else None
                })

    # 3. Create independent Generation Job
    job = GenerationJob(
        template_id=t.id,
        template_version=t.version,
        status="processing"
    )
    db.add(job)
    db.flush()

    # Snapshot values (FR-14)
    for var in t.variables:
        val = req.values.get(var.id) or req.values.get(var.key) or var.default_value or ""
        db.add(GenerationValue(
            job_id=job.id,
            variable_id=var.id,
            variable_key=var.key,
            value=val
        ))

    # 4. Create working copy and execute replacements
    working_copy = StorageManager.create_working_copy(original_file_path, prefix=f"job_{job.id[:8]}")

    try:
        if doc.format == "docx":
            DocxReplacer.apply_replacements(working_copy, approved_replacements)
        else:
            PdfReplacer.apply_replacements(working_copy, approved_replacements)

        # 5. Move working copy to generated/
        final_gen_filename = f"gen_{job.id}.{doc.format}"
        final_gen_path = settings.generated_path / final_gen_filename
        import shutil
        shutil.move(str(working_copy), str(final_gen_path))

        # 6. Post-generation validation (FR-10, Section 11)
        val_report = PostGeneratorValidator.validate(
            generated_path=final_gen_path,
            fmt=doc.format,
            intended_replacements=approved_replacements,
            excluded_texts=excluded_texts
        )

        job.status = "completed" if val_report.status != "failed" else "failed"
        job.validation_report = val_report.model_dump()
        if val_report.status == "failed":
            job.error_code = AppErrorCode.GENERATION_VALIDATION_FAILED
            job.error_message = "Post-generation validation failed. Check issues list."

        gen_sha256 = StorageManager.compute_sha256(final_gen_path)
        gen_doc = GeneratedDocument(
            job_id=job.id,
            format=doc.format,
            storage_path=str(final_gen_path),
            sha256=gen_sha256,
            validation_status=val_report.status
        )
        db.add(gen_doc)
        db.commit()

        log_event("DOCUMENT_GENERATED", job.id, f"status={job.status}")

        return GenerationJobResponse(
            id=job.id,
            template_id=job.template_id,
            template_version=job.template_version,
            status=job.status,
            created_at=job.created_at,
            error_code=job.error_code,
            error_message=job.error_message,
            validation_report=val_report,
            download_url=f"/api/v1/generations/{job.id}/download" if job.status == "completed" else None
        )

    except Exception as e:
        if working_copy.exists():
            try:
                working_copy.unlink()
            except Exception:
                pass
        job.status = "failed"
        job.error_code = getattr(e, "code", "GENERATION_ERROR")
        job.error_message = str(e)
        db.commit()
        raise e
