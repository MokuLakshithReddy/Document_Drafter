from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class ExtractedRun(BaseModel):
    run_index: int
    text: str
    bold: Optional[bool] = False
    italic: Optional[bool] = False
    underline: Optional[bool] = False
    font_name: Optional[str] = None
    font_size_pt: Optional[float] = None

class ExtractedUnit(BaseModel):
    """
    A paragraph, table cell paragraph, header paragraph, or PDF text span.
    """
    container_id: str # e.g. body/p[0], table[0]/r[0]/c[1]/p[0], header[0]/p[0], page[1]/b[0]
    kind: str # paragraph, table_cell, header, footer, pdf_block
    full_text: str
    runs: List[ExtractedRun] = []
    page: Optional[int] = None
    bbox: Optional[List[float]] = None

class ExtractedDocument(BaseModel):
    document_id: str
    format: str # docx or pdf
    units: List[ExtractedUnit]
    raw_text: str
    total_paragraphs: int = 0
    total_tables: int = 0
    has_headers_footers: bool = False
    is_scanned: bool = False
    scan_warning: Optional[str] = None
