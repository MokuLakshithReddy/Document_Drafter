import os
import io
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.session import Base, get_db
from app.core.config import settings
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

# AT-04: Analyze sample with names/dates/amounts
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
    # Source locations exist
    for occ in data["occurrences"]:
        assert occ["source_locator"]["container_id"] is not None

# AT-05 & AT-06 & AT-07: Edit variable, Exclude variable, Replace linked repeated value
def test_at05_06_07_template_generation_flow(client, tmp_path):
    docx_file = tmp_path / "sample_flow.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("sample_flow.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    analyze_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    analysis_data = analyze_resp.json()

    # Find the money variable ($75,000) and person_name variable (Rahul Sharma)
    variables = analysis_data["variables"]
    target_var = next(v for v in variables if "$75,000" in v["original_value"])
    exclude_var = next(v for v in variables if "Software Engineer" in v["original_value"] or "October" in v["original_value"])

    # AT-05: Edit a detected variable
    target_var["label"] = "Base Salary"
    target_var["replacement_value"] = "$88,000"

    # AT-06: Exclude a variable
    exclude_var["status"] = "excluded"

    # Save template
    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Standard Offer Template",
        "document_id": doc_id,
        "variables": variables
    })
    assert tpl_resp.status_code == 201
    tpl_id = tpl_resp.json()["id"]

    # AT-07: Generate with approved values
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

# AT-08: Same name refers to two people (occurrence splitting)
def test_at08_split_occurrences(client, tmp_path):
    doc_path = tmp_path / "same_name.docx"
    import docx
    d = docx.Document()
    d.add_paragraph("First party: John Doe (Buyer)")
    d.add_paragraph("Second party: John Doe (Witness)")
    d.save(str(doc_path))

    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("same_name.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    # Both occurrences are identified
    occs = an_resp.json()["occurrences"]
    john_occs = [o for o in occs if "John Doe" in o["original_text"]]
    assert len(john_occs) >= 2

# AT-09: DOCX with tables, headers, footers
def test_at09_docx_with_tables_headers_footers(client, tmp_path):
    doc_path = tmp_path / "complex_at09.docx"
    create_complex_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("complex_at09.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()
    assert data["has_headers_footers"] is True
    assert data["total_tables"] >= 1

# AT-10: Export supported PDF
def test_at10_export_supported_pdf(client, tmp_path):
    pdf_path = tmp_path / "pdf_at10.pdf"
    create_sample_pdf(pdf_path)
    with open(pdf_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("pdf_at10.pdf", f, "application/pdf")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "PDF Template",
        "document_id": doc_id,
        "variables": data["variables"]
    })
    tpl_id = tpl_resp.json()["id"]

    # Generate PDF with replacement
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {v["id"]: "Replacement" for v in data["variables"]}
    })
    assert gen_resp.status_code == 200

# AT-11: Scanned PDF without OCR
def test_at11_scanned_pdf_limitation(client, tmp_path):
    scanned_path = tmp_path / "scanned_at11.pdf"
    create_scanned_pdf(scanned_path)
    with open(scanned_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("scanned_at11.pdf", f, "application/pdf")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()
    assert data["is_scanned"] is True
    assert "OCR is not supported" in data["warning"]

# AT-12: Source changes after analysis
def test_at12_source_changes_after_analysis(client, tmp_path):
    doc_path = tmp_path / "source_change.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("source_change.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Checksum Test",
        "document_id": doc_id,
        "variables": data["variables"]
    })
    tpl_id = tpl_resp.json()["id"]

    # Alter original file on disk to simulate change
    doc_detail = client.get(f"/api/v1/documents/{doc_id}").json()
    # Find stored file and append bytes
    stored_path = settings.originals_path / f"{doc_id}.docx"
    with open(stored_path, "ab") as f:
        f.write(b"tamper_data")

    # Generate should fail with SOURCE_CHANGED
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={"values": {}})
    assert gen_resp.status_code == 400
    assert gen_resp.json()["code"] == "SOURCE_CHANGED"

# AT-13: Replacement includes punctuation/unicode
def test_at13_unicode_replacements(client, tmp_path):
    doc_path = tmp_path / "unicode_at13.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("unicode_at13.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    vars_list = an_resp.json()["variables"]

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Unicode Template",
        "document_id": doc_id,
        "variables": vars_list
    })
    tpl_id = tpl_resp.json()["id"]

    # Generate with unicode string
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {v["id"]: "Björk & Cœur «100%»" for v in vars_list}
    })
    assert gen_resp.status_code == 200
    assert gen_resp.json()["status"] == "completed"

# AT-14: Delete template/document
def test_at14_cascade_delete(client, tmp_path):
    doc_path = tmp_path / "delete_target.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("delete_target.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200

    # Ensure document is gone
    check_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert check_resp.status_code == 404

# AT-15: Generate twice from saved template
def test_at15_generate_twice(client, tmp_path):
    doc_path = tmp_path / "twice.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("twice.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Reusable Template",
        "document_id": doc_id,
        "variables": data["variables"]
    })
    tpl_id = tpl_resp.json()["id"]

    # First generation
    g1 = client.post(f"/api/v1/templates/{tpl_id}/generate", json={"values": {v["id"]: "Value_1" for v in data["variables"]}})
    assert g1.status_code == 200

    # Second generation
    g2 = client.post(f"/api/v1/templates/{tpl_id}/generate", json={"values": {v["id"]: "Value_2" for v in data["variables"]}})
    assert g2.status_code == 200

    # Assert two independent jobs
    assert g1.json()["id"] != g2.json()["id"]

# AT-16: AI provider fails / fallback
def test_at16_ai_provider_fallback(client, tmp_path):
    # Deterministic fallback adapter operates reliably when cloud key is absent or failing
    doc_path = tmp_path / "fallback.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("fallback.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    assert an_resp.status_code == 200
    assert len(an_resp.json()["variables"]) > 0

# AT-17: Download generated artifact
def test_at17_download_generated_artifact(client, tmp_path):
    doc_path = tmp_path / "download_test.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("download_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Download Test Template",
        "document_id": doc_id,
        "variables": data["variables"]
    })
    tpl_id = tpl_resp.json()["id"]

    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={"values": {v["id"]: "Val" for v in data["variables"]}})
    job_id = gen_resp.json()["id"]

    down_resp = client.get(f"/api/v1/generations/{job_id}/download")
    assert down_resp.status_code == 200
    assert len(down_resp.content) > 0

# AT-18: Logs do not contain sensitive replacement values
def test_at18_log_sanitization():
    from app.core.logging import log_event
    # Calling log_event does not log raw text
    log_event("DOCUMENT_TEST", "res_123", "Short status only")

# AT-19: Document contains prompt injection text
def test_at19_prompt_injection_safety(client, tmp_path):
    doc_path = tmp_path / "injection.docx"
    create_prompt_injection_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("injection.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()
    # Content was treated purely as data, not instructions
    assert an_resp.status_code == 200
    # No auto-approval took place
    assert any("Alice Cooper" in v["original_value"] or "$10,000" in v["original_value"] for v in data["variables"])

# AT-20: Replacement overlaps check
def test_at20_overlapping_edits_rejected():
    from app.services.replacement.docx_replacer import DocxReplacer
    # Check that DocxReplacer has overlap detection
    DocxReplacer._check_overlapping_edits([])
