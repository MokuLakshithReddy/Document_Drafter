import os
import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import docx
import pymupdf as fitz

from app.main import app
from app.db.session import Base, get_db
from app.core.config import settings
from app.core.errors import AppException, AppErrorCode
from app.api.v1.analysis import _analysis_cache
from app.services.replacement.docx_replacer import DocxReplacer
from app.services.replacement.pdf_replacer import PdfReplacer
from app.services.validation.post_generator_validator import PostGeneratorValidator
from tests.fixtures.fixture_builder import (
    create_sample_docx,
    create_complex_docx,
    create_sample_pdf,
    create_scanned_pdf,
    create_prompt_injection_docx,
    create_malformed_file
)

# Test in-memory SQLite database
TEST_DB_URL = "sqlite:///./test_acceptance.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="module", autouse=True)
def setup_test_db(tmp_path_factory):
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    if Path("./test_acceptance.db").exists():
        try:
            Path("./test_acceptance.db").unlink()
        except Exception:
            pass

@pytest.fixture
def client():
    return TestClient(app)

# AT-01: Upload valid DOCX
def test_at01_upload_valid_docx(client, tmp_path):
    docx_file = tmp_path / "valid.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        resp = client.post("/api/v1/documents", files={"file": ("valid.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert resp.status_code == 201
    data = resp.json()
    assert data["format"] == "docx"
    assert "sha256" in data
    assert "id" in data

# AT-02: Upload text-based PDF
def test_at02_upload_text_based_pdf(client, tmp_path):
    pdf_file = tmp_path / "valid.pdf"
    create_sample_pdf(pdf_file)
    with open(pdf_file, "rb") as f:
        resp = client.post("/api/v1/documents", files={"file": ("valid.pdf", f, "application/pdf")})
    assert resp.status_code == 201
    data = resp.json()
    assert data["format"] == "pdf"
    assert data["page_count"] >= 1

# AT-03: Upload renamed/corrupt/unsupported file
def test_at03_upload_corrupt_file(client, tmp_path):
    bad_file = tmp_path / "corrupt.docx"
    create_malformed_file(bad_file)
    with open(bad_file, "rb") as f:
        resp = client.post("/api/v1/documents", files={"file": ("corrupt.docx", f, "application/octet-stream")})
    assert resp.status_code == 400
    assert resp.json()["code"] in ["INVALID_ARCHIVE", "UNSUPPORTED_FORMAT"]

# AT-04: Analyze sample with names/dates/amounts - verify initialized as pending
def test_at04_analyze_sample(client, tmp_path):
    docx_file = tmp_path / "sample_at04.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("sample_at04.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    analyze_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    assert analyze_resp.status_code == 200
    data = analyze_resp.json()
    assert len(data["variables"]) > 0
    assert len(data["occurrences"]) > 0
    # Mandatory requirement: Newly detected variables MUST be initialized as pending
    for v in data["variables"]:
        assert v["status"] == "pending", f"Variable {v['key']} should be pending by default"
    for occ in data["occurrences"]:
        assert occ["source_locator"]["container_id"] is not None

# AT-05 & AT-06 & AT-07: Edit variable, Exclude variable, Approval-First Replacement
def test_at05_06_07_template_generation_flow(client, tmp_path):
    docx_file = tmp_path / "sample_flow.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("sample_flow.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    analyze_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    analysis_data = analyze_resp.json()

    variables = analysis_data["variables"]
    target_var = next(v for v in variables if "$75,000" in v["original_value"])
    exclude_var = next(v for v in variables if "Software Engineer" in v["original_value"] or "October" in v["original_value"])

    # AT-05: Edit and APPROVE target variable
    target_var["label"] = "Base Salary"
    target_var["replacement_value"] = "$88,000"
    target_var["status"] = "approved"

    # AT-06: Explicitly exclude another variable
    exclude_var["status"] = "excluded"

    # Save template
    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Standard Offer Template",
        "document_id": doc_id,
        "variables": variables,
        "occurrences": analysis_data["occurrences"]
    })
    assert tpl_resp.status_code == 201
    tpl_id = tpl_resp.json()["id"]

    # AT-07: Generate with approved value
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {
            target_var["id"]: "$88,000"
        }
    })
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["status"] == "completed"
    assert gen_data["validation_report"]["status"] in ["passed", "warning"]
    assert gen_data["validation_report"]["protected_content_verified"] is True

# Test Approval-First: Pending variables must NOT be replaced even if value is passed
def test_approval_first_pending_variable_untouched(client, tmp_path):
    doc_path = tmp_path / "pending_test.docx"
    d = docx.Document()
    d.add_paragraph("Employee: Rahul Sharma")
    d.add_paragraph("Starting Date: October 26, 2026")
    d.save(str(doc_path))

    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("pending_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    vars_list = an_resp.json()["variables"]

    # Leave all variables as 'pending'
    for v in vars_list:
        assert v["status"] == "pending"

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Pending Test Template",
        "document_id": doc_id,
        "variables": vars_list,
        "occurrences": an_resp.json()["occurrences"]
    })
    tpl_id = tpl_resp.json()["id"]

    # Attempt to pass replacement for pending variable
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {
            vars_list[0]["id"]: "UNAPPROVED_REPLACEMENT_VALUE"
        }
    })
    assert gen_resp.status_code == 200
    job_id = gen_resp.json()["id"]

    # Download and verify unapproved text is completely untouched in actual output file
    down_resp = client.get(f"/api/v1/generations/{job_id}/download")
    out_docx_path = tmp_path / "out_pending.docx"
    with open(out_docx_path, "wb") as f:
        f.write(down_resp.content)

    doc_out = docx.Document(str(out_docx_path))
    full_text = " ".join(p.text for p in doc_out.paragraphs)
    assert "UNAPPROVED_REPLACEMENT_VALUE" not in full_text
    assert vars_list[0]["original_value"] in full_text

# Exact DOCX occurrence replacement: Repeated identical text in one paragraph
def test_exact_docx_repeated_text_in_one_paragraph(tmp_path):
    doc_path = tmp_path / "repeated_same_para.docx"
    d = docx.Document()
    # Paragraph contains the exact same name twice
    p = d.add_paragraph("John Doe was appointed as Director, and John Doe signed the document.")
    d.save(str(doc_path))

    # occ 1: John Doe at offset 0..8
    # occ 2: John Doe at offset 38..46
    replacements = [
        {
            "occurrence_id": "occ_002",
            "container_id": "body/p[0]",
            "original_text": "John Doe",
            "new_text": "Alice Smith",
            "char_start": 40,
            "char_end": 48
        }
    ]

    res = DocxReplacer.apply_replacements(doc_path, replacements)
    assert res["applied_count"] == 1

    # Verify generated document
    gen_doc = docx.Document(str(doc_path))
    result_text = gen_doc.paragraphs[0].text
    # Occ 1 MUST remain 'John Doe', Occ 2 MUST be 'Alice Smith'
    assert result_text == "John Doe was appointed as Director, and Alice Smith signed the document."

# DOCX text split across formatting runs
def test_docx_text_split_across_formatting_runs(tmp_path):
    doc_path = tmp_path / "split_runs.docx"
    d = docx.Document()
    p = d.add_paragraph()
    r1 = p.add_run("Rahul ")
    r2 = p.add_run("Sharma")
    r2.bold = True
    p.add_run(" is hereby appointed.")
    d.save(str(doc_path))

    replacements = [
        {
            "occurrence_id": "occ_split",
            "container_id": "body/p[0]",
            "original_text": "Rahul Sharma",
            "new_text": "Alex Morgan",
            "char_start": 0,
            "char_end": 12
        }
    ]

    res = DocxReplacer.apply_replacements(doc_path, replacements)
    assert res["applied_count"] == 1

    gen_doc = docx.Document(str(doc_path))
    assert "Alex Morgan is hereby appointed." in gen_doc.paragraphs[0].text

# Overlapping edits rejected with AppErrorCode.OVERLAPPING_EDIT
def test_overlapping_edits_rejected():
    with pytest.raises(AppException) as excinfo:
        DocxReplacer._check_overlapping_edits([
            {
                "occurrence_id": "occ_1",
                "container_id": "body/p[0]",
                "original_text": "Rahul Sharma",
                "new_text": "Alice",
                "char_start": 0,
                "char_end": 12
            },
            {
                "occurrence_id": "occ_2",
                "container_id": "body/p[0]",
                "original_text": "Sharma is",
                "new_text": "Bob",
                "char_start": 6,
                "char_end": 15
            }
        ])
    assert excinfo.value.code == AppErrorCode.OVERLAPPING_EDIT

# PDF repeated text on same page: target only specific bounding box
def test_pdf_repeated_occurrences_bbox_targeting(tmp_path):
    pdf_path = tmp_path / "pdf_repeated.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    # Write same name at two different positions
    p1 = fitz.Point(72, 100)
    p2 = fitz.Point(72, 200)
    page.insert_text(p1, "John Doe is the contractor.", fontsize=11)
    page.insert_text(p2, "John Doe is the signatory.", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    # Search for rects
    chk_doc = fitz.open(pdf_path)
    rects = chk_doc[0].search_for("John Doe")
    chk_doc.close()
    assert len(rects) == 2

    # Target ONLY rect 2 (the signatory)
    target_rect = rects[1]
    replacements = [
        {
            "occurrence_id": "occ_pdf_2",
            "container_id": "page[0]",
            "original_text": "John Doe",
            "new_text": "Elena Rostova",
            "page": 0,
            "bbox": [target_rect.x0, target_rect.y0, target_rect.x1, target_rect.y1]
        }
    ]

    res = PdfReplacer.apply_replacements(pdf_path, replacements)
    assert res["applied_count"] == 1

    # Inspect generated PDF
    out_doc = fitz.open(pdf_path)
    page_text = out_doc[0].get_text()
    out_doc.close()

    # First instance must remain John Doe, second instance must be Elena Rostova
    assert "John Doe" in page_text, "Unapproved first John Doe must remain intact"
    assert "Elena Rostova" in page_text, "Approved second John Doe must be replaced"

# Format conversion: DOCX -> PDF
def test_docx_to_pdf_conversion(client, tmp_path):
    docx_file = tmp_path / "convert_doc.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("convert_doc.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    vars_list = an_resp.json()["variables"]

    # Approve one variable
    vars_list[0]["status"] = "approved"
    vars_list[0]["replacement_value"] = "Vikram Patel"

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Convert Template",
        "document_id": doc_id,
        "variables": vars_list,
        "occurrences": an_resp.json()["occurrences"]
    })
    tpl_id = tpl_resp.json()["id"]

    # Request PDF output for DOCX source
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {vars_list[0]["id"]: "Vikram Patel"},
        "output_format": "pdf"
    })
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["output_format"] == "pdf"
    assert gen_data["status"] == "completed"

    # Download and verify PDF binary header
    down_resp = client.get(f"/api/v1/generations/{gen_data['id']}/download")
    assert down_resp.status_code == 200
    assert down_resp.content.startswith(b"%PDF-")

# Format rejection: PDF -> DOCX is rejected with 400 UNSUPPORTED_FORMAT
def test_pdf_to_docx_rejected(client, tmp_path):
    pdf_path = tmp_path / "src_pdf.pdf"
    create_sample_pdf(pdf_path)
    with open(pdf_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("src_pdf.pdf", f, "application/pdf")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    vars_list = an_resp.json()["variables"]
    for v in vars_list:
        v["status"] = "approved"

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "PDF Template",
        "document_id": doc_id,
        "variables": vars_list,
        "occurrences": an_resp.json()["occurrences"]
    })
    tpl_id = tpl_resp.json()["id"]

    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {},
        "output_format": "docx"
    })
    assert gen_resp.status_code == 400
    assert gen_resp.json()["code"] == "UNSUPPORTED_FORMAT"

# Post-generator validation: fails when unapproved container content is altered
def test_post_generator_validator_fails_on_unapproved_alteration(tmp_path):
    src_docx = tmp_path / "src_clean.docx"
    d_src = docx.Document()
    d_src.add_paragraph("Approved line: Replace Me")
    d_src.add_paragraph("Protected line: Unchanged Original Content")
    d_src.save(str(src_docx))

    gen_docx = tmp_path / "gen_tampered.docx"
    d_gen = docx.Document()
    d_gen.add_paragraph("Approved line: Replacement Applied")
    # Tamper with the protected line!
    d_gen.add_paragraph("Protected line: TAMPERED UNAPPROVED CONTENT")
    d_gen.save(str(gen_docx))

    intended = [
        {
            "occurrence_id": "occ_1",
            "container_id": "body/p[0]",
            "original_text": "Replace Me",
            "new_text": "Replacement Applied"
        }
    ]

    report = PostGeneratorValidator.validate(
        generated_path=gen_docx,
        fmt="docx",
        intended_replacements=intended,
        excluded_texts=[],
        source_path=src_docx
    )

    assert report.status == "failed"
    assert any(i.code == "UNAPPROVED_CONTENT_ALTERED" for i in report.issues)

# Application restart and template reuse: persists analysis in database
def test_restart_persistence_and_template_reuse(client, tmp_path):
    docx_file = tmp_path / "restart_test.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("restart_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    # Run analysis
    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    assert an_resp.status_code == 200

    # Simulate restart by clearing in-memory cache completely
    _analysis_cache.clear()

    # Request analysis result after restart
    res_resp = client.get(f"/api/v1/analysis/{doc_id}")
    assert res_resp.status_code == 200
    recovered_data = res_resp.json()
    assert len(recovered_data["variables"]) > 0

    # Successfully save template from recovered analysis
    target_var = recovered_data["variables"][0]
    target_var["status"] = "approved"
    target_var["replacement_value"] = "New Director"

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Persisted Template",
        "document_id": doc_id,
        "variables": recovered_data["variables"]
    })
    assert tpl_resp.status_code == 201
    tpl_id = tpl_resp.json()["id"]

    # Generate document from persisted template
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {target_var["id"]: "New Director"}
    })
    assert gen_resp.status_code == 200
    assert gen_resp.json()["status"] == "completed"

# Checksum validation: source document changes after template creation
def test_stale_source_checksum_fails(client, tmp_path):
    doc_path = tmp_path / "stale_checksum.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("stale_checksum.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    vars_list = an_resp.json()["variables"]

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Checksum Verification Template",
        "document_id": doc_id,
        "variables": vars_list
    })
    tpl_id = tpl_resp.json()["id"]

    # Tamper with the source document in storage
    stored_path = settings.originals_path / f"{doc_id}.docx"
    with open(stored_path, "ab") as f:
        f.write(b"\n#stale_bytes")

    # Generation should fail with SOURCE_CHANGED
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={"values": {}})
    assert gen_resp.status_code == 400
    assert gen_resp.json()["code"] == "SOURCE_CHANGED"

# Cascade delete cleans up physical files and database records
def test_cascade_delete_and_file_cleanup(client, tmp_path):
    doc_path = tmp_path / "cleanup_target.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("cleanup_target.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    stored_file = settings.originals_path / f"{doc_id}.docx"
    assert stored_file.exists()

    # Delete
    del_resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200

    # Verify physical file deleted
    assert not stored_file.exists()

    # Verify database record deleted
    get_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 404
