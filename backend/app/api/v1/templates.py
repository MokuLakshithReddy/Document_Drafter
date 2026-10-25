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
from app.services.generation.format_converter import FormatConverter
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
            status=v.status or "active",
            default_value=v.replacement_value.strip() if (v.replacement_value and isinstance(v.replacement_value, str) and v.replacement_value.strip()) else None,
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
            if loc.get("container_id") == "auto" and doc.id in _analysis_cache:
                matched_occ = next((o for o in _analysis_cache[doc.id].occurrences if o.id == occ_id), None)
                if matched_occ:
                    loc = matched_occ.source_locator.model_dump()
            if loc.get("container_id") == "auto" and doc.analysis_json and "occurrences" in doc.analysis_json:
                matched_raw = next((o for o in doc.analysis_json["occurrences"] if o.get("id") == occ_id), None)
                if not matched_raw:
                    # Fallback match by original_text
                    matched_raw = next((o for o in doc.analysis_json["occurrences"] if o.get("original_text") == v.original_value), None)
                if matched_raw:
                    loc = matched_raw.get("source_locator", loc)

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
            raw_loc = o.source_locator if isinstance(o.source_locator, dict) else {}
            occ_dtos.append(
                OccurrenceDTO(
                    id=o.id,
                    variable_id=v.id,
                    source_locator=SourceLocator(
                        kind=raw_loc.get("kind", "paragraph"),
                        container_id=raw_loc.get("container_id", "body/p[0]"),
                        run_index=raw_loc.get("run_index"),
                        char_start=raw_loc.get("char_start"),
                        char_end=raw_loc.get("char_end"),
                        bbox=raw_loc.get("bbox"),
                        page=raw_loc.get("page")
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

    # 1. Output format resolution and support check
    req_fmt = (req.output_format or doc.format).lower()
    if doc.format == "pdf" and req_fmt == "docx":
        raise AppException(
            code=AppErrorCode.UNSUPPORTED_FORMAT,
            message="PDF to DOCX conversion is not supported. Please select PDF output format."
        )
    target_format = req_fmt if req_fmt in ["docx", "pdf"] else doc.format

    # 2. Source Checksum validation
    current_checksum = StorageManager.compute_sha256(original_file_path)
    if current_checksum != t.source_checksum:
        raise AppException(
            code=AppErrorCode.SOURCE_CHANGED,
            message="Source document has changed since template creation. Please re-analyze the document.",
            details={"template_checksum": t.source_checksum, "current_checksum": current_checksum}
        )

    # 3. Build replacement instructions according to the simple rule:
    # If the user enters a non-empty new value, replace the corresponding original value.
    # If the user leaves the field blank, null, or omits it, leave the original document content unchanged.
    active_replacements: List[Dict[str, Any]] = []
    unmodified_original_texts: List[str] = []

    for var in t.variables:
        # Resolve raw value provided by variable id, client_id, or key
        raw_val = None
        if req.values:
            if var.id in req.values:
                raw_val = req.values[var.id]
            elif var.client_id and var.client_id in req.values:
                raw_val = req.values[var.client_id]
            elif var.key in req.values:
                raw_val = req.values[var.key]

        # Missing, null, empty, or whitespace-only means "keep original unchanged"
        if raw_val is None or not isinstance(raw_val, str) or not raw_val.strip():
            for occ in var.occurrences:
                unmodified_original_texts.append(occ.original_text)
            continue

        new_val = raw_val.strip()

        # Build replacement entries for each occurrence with exact locators
        for occ in var.occurrences:
            loc = occ.source_locator or {}
            active_replacements.append({
                "occurrence_id": occ.id,
                "container_id": loc.get("container_id", "body/p[0]"),
                "kind": loc.get("kind", "paragraph"),
                "original_text": occ.original_text,
                "new_text": new_val,
                "run_index": loc.get("run_index"),
                "char_start": loc.get("char_start"),
                "char_end": loc.get("char_end"),
                "page": loc.get("page"),
                "bbox": loc.get("bbox")
            })

    # 4. Create independent Generation Job
    job = GenerationJob(
        template_id=t.id,
        template_version=t.version,
        output_format=target_format,
        status="processing"
    )
    db.add(job)
    db.flush()

    # Snapshot values (FR-14)
    for var in t.variables:
        val = None
        if req.values:
            if var.id in req.values:
                val = req.values[var.id]
            elif var.client_id and var.client_id in req.values:
                val = req.values[var.client_id]
            elif var.key in req.values:
                val = req.values[var.key]
        val_str = str(val).strip() if val and isinstance(val, str) else ""
        db.add(GenerationValue(
            job_id=job.id,
            variable_id=var.id,
            variable_key=var.key,
            value=val_str
        ))

    # 5. Create working copy and execute replacements
    working_copy = StorageManager.create_working_copy(original_file_path, prefix=f"job_{job.id[:8]}")

    try:
        final_gen_filename = f"gen_{job.id}.{target_format}"
        final_gen_path = settings.generated_path / final_gen_filename

        if doc.format == "docx":
            DocxReplacer.apply_replacements(working_copy, active_replacements)
            if target_format == "pdf":
                # Convert DOCX working copy to PDF using FormatConverter
                FormatConverter.convert_docx_to_pdf(working_copy, final_gen_path)
                try:
                    working_copy.unlink(missing_ok=True)
                except Exception:
                    pass
            else:
                import shutil
                shutil.move(str(working_copy), str(final_gen_path))
        else:
            PdfReplacer.apply_replacements(working_copy, active_replacements)
            import shutil
            shutil.move(str(working_copy), str(final_gen_path))

        # 6. Post-generation validation (FR-10, Section 11)
        val_report = PostGeneratorValidator.validate(
            generated_path=final_gen_path,
            fmt=target_format,
            intended_replacements=active_replacements,
            unmodified_original_texts=unmodified_original_texts,
            source_path=original_file_path if target_format == doc.format else None
        )

        job.status = "completed" if val_report.status != "failed" else "failed"
        job.validation_report = val_report.model_dump()
        if val_report.status == "failed":
            job.error_code = AppErrorCode.GENERATION_VALIDATION_FAILED
            job.error_message = "Post-generation validation failed. Check issues list."

        gen_sha256 = StorageManager.compute_sha256(final_gen_path)
        gen_doc = GeneratedDocument(
            job_id=job.id,
            format=target_format,
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
            output_format=target_format,
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
