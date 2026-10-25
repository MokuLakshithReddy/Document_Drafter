from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

# Base & Document Schemas
class DocumentCreateResponse(BaseModel):
    id: str
    filename: str
    format: str
    sha256: str
    created_at: datetime
    status: str
    page_count: int

class DocumentDetailResponse(BaseModel):
    id: str
    filename: str
    format: str
    sha256: str
    created_at: datetime
    status: str
    page_count: int
    error_message: Optional[str] = None

# Occurrence Schema
class SourceLocator(BaseModel):
    kind: str # paragraph, table_cell, header, footer, pdf_block
    container_id: str # e.g. body/p[2], table[0]/r[1]/c[2]/p[0], header[0]/p[0], page[0]
    run_index: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    bbox: Optional[List[float]] = None # [x0, y0, x1, y1] for PDF
    page: Optional[int] = None

class OccurrenceDTO(BaseModel):
    id: str
    variable_id: Optional[str] = None
    source_locator: SourceLocator
    original_text: str
    status: str = "active" # active, excluded

# Variable Schema
class VariableDTO(BaseModel):
    id: str
    key: str
    label: str
    type: str # person_name, organization, date, address, money, phone, email, identifier, role, location, custom
    original_value: str
    replacement_value: Optional[str] = ""
    occurrence_ids: List[str] = Field(default_factory=list)
    confidence: Optional[float] = 1.0
    reason: Optional[str] = None
    required: bool = True
    status: str = "approved" # approved, excluded

# Analysis Schemas
class AnalysisResultDTO(BaseModel):
    document_id: str
    document_type: str
    extracted_text_preview: str
    total_paragraphs: int
    total_tables: int
    has_headers_footers: bool
    is_scanned: bool = False
    warning: Optional[str] = None
    occurrences: List[OccurrenceDTO]
    variables: List[VariableDTO]

# Template Schemas
class SaveTemplateRequest(BaseModel):
    name: str
    document_id: str
    variables: List[VariableDTO]
    occurrences: Optional[List[OccurrenceDTO]] = None

class TemplateSummaryDTO(BaseModel):
    id: str
    name: str
    source_document_id: str
    source_filename: str
    source_format: str
    version: int
    status: str
    created_at: datetime
    variable_count: int

class TemplateDetailDTO(BaseModel):
    id: str
    name: str
    source_document_id: str
    source_filename: str
    source_format: str
    source_checksum: str
    version: int
    status: str
    created_at: datetime
    variables: List[VariableDTO]
    occurrences: List[OccurrenceDTO]

class UpdateVariableRequest(BaseModel):
    key: Optional[str] = None
    label: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    required: Optional[bool] = None
    replacement_value: Optional[str] = None
    occurrence_ids: Optional[List[str]] = None

# Generation Schemas
class GenerateDocumentRequest(BaseModel):
    values: Dict[str, str] # map of variable_id or variable_key -> new value
    output_format: Optional[str] = "docx" # docx or pdf

class ValidationIssue(BaseModel):
    severity: str # error, warning
    code: str
    message: str
    location: Optional[str] = None

class ValidationReport(BaseModel):
    status: str # passed, warning, failed
    intended_replacements_count: int
    verified_replacements_count: int
    protected_content_verified: bool
    issues: List[ValidationIssue] = Field(default_factory=list)

class GenerationJobResponse(BaseModel):
    id: str
    template_id: str
    template_version: int
    status: str
    created_at: datetime
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    validation_report: Optional[ValidationReport] = None
    download_url: Optional[str] = None

# Settings Schemas
class AppSettingsDTO(BaseModel):
    ai_provider: str
    has_gemini_key: bool
    has_openai_key: bool
    max_upload_size_mb: int
    max_page_limit: int
    file_retention_days: int
    storage_dir: str

class UpdateSettingsRequest(BaseModel):
    ai_provider: Optional[str] = None
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    file_retention_days: Optional[int] = None
