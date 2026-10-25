import pytest
from pathlib import Path
from tests.fixtures.fixture_builder import create_sample_pdf, create_scanned_pdf, create_sample_docx
from app.services.extraction.pdf_extractor import PdfExtractor
from app.services.extraction.docx_extractor import DocxExtractor
from app.services.analysis.candidate_detector import CandidateDetector

def test_pdf_extraction_with_bboxes(tmp_path: Path):
    pdf_path = tmp_path / "sample.pdf"
    create_sample_pdf(pdf_path)

    extracted = PdfExtractor.extract(pdf_path, "pdf_123")
    assert extracted.format == "pdf"
    assert extracted.is_scanned is False
    assert len(extracted.units) > 0

    # Ensure bounding boxes are present
    unit = extracted.units[0]
    assert unit.bbox is not None
    assert len(unit.bbox) == 4
    assert unit.page == 0

def test_scanned_pdf_detection(tmp_path: Path):
    pdf_path = tmp_path / "scanned.pdf"
    create_scanned_pdf(pdf_path)

    extracted = PdfExtractor.extract(pdf_path, "scanned_123")
    assert extracted.is_scanned is True
    assert extracted.scan_warning is not None
    assert "OCR is not supported" in extracted.scan_warning

def test_candidate_detector_entities(tmp_path: Path):
    doc_path = tmp_path / "sample.docx"
    create_sample_docx(doc_path)

    extracted = DocxExtractor.extract(doc_path, "sample_123")
    occurrences, variables = CandidateDetector.detect(extracted)

    assert len(occurrences) > 0
    assert len(variables) > 0

    # Check extracted types
    types = {v.type for v in variables}
    assert "date" in types # October 25, 2026
    assert "money" in types # $75,000
    assert "email" in types # rahul.sharma@example.com
    assert "phone" in types # (555) 234-5678

    # Verify occurrence IDs are well-formed
    for occ in occurrences:
        assert occ.id.startswith("occ_")
        assert occ.source_locator.container_id is not None
