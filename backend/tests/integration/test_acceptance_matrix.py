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
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)
    app.dependency_overrides.pop(get_db, None)
    if Path("./test_acceptance.db").exists():
        try:
            Path("./test_acceptance.db").unlink()
        except Exception:
            pass

@pytest.fixture
def client():
    return TestClient(app)

# 1. Upload valid DOCX
def test_upload_valid_docx(client, tmp_path):
    docx_file = tmp_path / "valid.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        resp = client.post("/api/v1/documents", files={"file": ("valid.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    assert resp.status_code == 201
    data = resp.json()
    assert data["format"] == "docx"
    assert "sha256" in data
    assert "id" in data

# 2. Upload text-based PDF
def test_upload_text_based_pdf(client, tmp_path):
    pdf_file = tmp_path / "valid.pdf"
    create_sample_pdf(pdf_file)
    with open(pdf_file, "rb") as f:
        resp = client.post("/api/v1/documents", files={"file": ("valid.pdf", f, "application/pdf")})
    assert resp.status_code == 201
    data = resp.json()
    assert data["format"] == "pdf"
    assert data["page_count"] >= 1

# 3. Upload malformed / corrupt file rejected
def test_upload_corrupt_file_rejected(client, tmp_path):
    bad_file = tmp_path / "corrupt.docx"
    create_malformed_file(bad_file)
    with open(bad_file, "rb") as f:
        resp = client.post("/api/v1/documents", files={"file": ("corrupt.docx", f, "application/octet-stream")})
    assert resp.status_code == 400
    assert resp.json()["code"] in ["INVALID_ARCHIVE", "UNSUPPORTED_FORMAT"]

# 4. Analyze document detects variables and occurrences
def test_analyze_document_detects_variables(client, tmp_path):
    docx_file = tmp_path / "sample_analysis.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("sample_analysis.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    analyze_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    assert analyze_resp.status_code == 200
    data = analyze_resp.json()
    assert len(data["variables"]) > 0
    assert len(data["occurrences"]) > 0
    for occ in data["occurrences"]:
        assert occ["source_locator"]["container_id"] is not None

# 5. One field changed while all other fields remain untouched
def test_one_field_changed_others_untouched(client, tmp_path):
    docx_file = tmp_path / "one_field_test.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("one_field_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()
    vars_list = data["variables"]

    # Target only the money variable ($75,000)
    money_var = next(v for v in vars_list if "$75,000" in v["original_value"])

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "One Field Template",
        "document_id": doc_id,
        "variables": vars_list,
        "occurrences": data["occurrences"]
    })
    tpl_id = tpl_resp.json()["id"]

    # Provide a value ONLY for money_var; leave all others omitted
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {
            money_var["id"]: "$95,000"
        }
    })
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["status"] == "completed"
    assert gen_data["validation_report"]["status"] in ["passed", "warning"]

    # Download and verify the actual document
    down_resp = client.get(f"/api/v1/generations/{gen_data['id']}/download")
    out_docx_path = tmp_path / "one_field_out.docx"
    with open(out_docx_path, "wb") as f:
        f.write(down_resp.content)

    doc_out = docx.Document(str(out_docx_path))
    full_text = " ".join(p.text for p in doc_out.paragraphs)

    # Replaced value MUST be present
    assert "$95,000" in full_text
    assert "$75,000" not in full_text

    # All unsupplied fields MUST remain unchanged
    assert "Rahul Sharma" in full_text
    assert "Software Engineer" in full_text
    assert "October 25, 2026" in full_text
    assert "rahul.sharma@example.com" in full_text

# 6. All fields blank: the document remains completely unchanged
def test_all_fields_blank_document_unchanged(client, tmp_path):
    docx_file = tmp_path / "all_blank_test.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("all_blank_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Blank Values Template",
        "document_id": doc_id,
        "variables": data["variables"],
        "occurrences": data["occurrences"]
    })
    tpl_id = tpl_resp.json()["id"]

    # Supply empty dict
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={"values": {}})
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["status"] == "completed"

    down_resp = client.get(f"/api/v1/generations/{gen_data['id']}/download")
    out_docx_path = tmp_path / "all_blank_out.docx"
    with open(out_docx_path, "wb") as f:
        f.write(down_resp.content)

    doc_orig = docx.Document(str(docx_file))
    doc_gen = docx.Document(str(out_docx_path))

    orig_paras = [p.text for p in doc_orig.paragraphs]
    gen_paras = [p.text for p in doc_gen.paragraphs]
    assert orig_paras == gen_paras

# 7. Missing, null, empty, and whitespace-only values do not blank original text
def test_missing_null_empty_whitespace_values(client, tmp_path):
    docx_file = tmp_path / "whitespace_test.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("whitespace_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    vars_list = an_resp.json()["variables"]

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Whitespace Test Template",
        "document_id": doc_id,
        "variables": vars_list,
        "occurrences": an_resp.json()["occurrences"]
    })
    tpl_id = tpl_resp.json()["id"]

    # Pass null, empty string, and whitespace-only
    values = {}
    if len(vars_list) > 0:
        values[vars_list[0]["id"]] = None
    if len(vars_list) > 1:
        values[vars_list[1]["id"]] = ""
    if len(vars_list) > 2:
        values[vars_list[2]["id"]] = "     "

    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={"values": values})
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["status"] == "completed"

    down_resp = client.get(f"/api/v1/generations/{gen_data['id']}/download")
    out_docx_path = tmp_path / "whitespace_out.docx"
    with open(out_docx_path, "wb") as f:
        f.write(down_resp.content)

    doc_out = docx.Document(str(out_docx_path))
    full_text = " ".join(p.text for p in doc_out.paragraphs)

    # None of the variables should have been blanked out!
    for v in vars_list[:3]:
        assert v["original_value"] in full_text

# 8. Repeated identical text in one paragraph (exact targeting)
def test_exact_docx_repeated_text_in_one_paragraph(tmp_path):
    doc_path = tmp_path / "repeated_same_para.docx"
    d = docx.Document()
    d.add_paragraph("John Doe was appointed as Director, and John Doe signed the document.")
    d.save(str(doc_path))

    # Replace only the second John Doe at offset 40..48
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

    gen_doc = docx.Document(str(doc_path))
    result_text = gen_doc.paragraphs[0].text
    assert result_text == "John Doe was appointed as Director, and Alice Smith signed the document."

# 9. Text split across formatting runs
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

# 10. DOCX tables, headers, footers
def test_docx_tables_headers_footers(client, tmp_path):
    doc_path = tmp_path / "complex_table_hdr.docx"
    create_complex_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("complex_table_hdr.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    data = an_resp.json()
    assert data["has_headers_footers"] is True
    assert data["total_tables"] >= 1

# 11. Overlapping edits rejected with OVERLAPPING_EDIT
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

# 12. PDF repeated text on same page: target only specific bounding box
def test_pdf_repeated_occurrences_bbox_targeting(tmp_path):
    pdf_path = tmp_path / "pdf_repeated.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text(fitz.Point(72, 100), "John Doe is the contractor.", fontsize=11)
    page.insert_text(fitz.Point(72, 200), "John Doe is the signatory.", fontsize=11)
    doc.save(str(pdf_path))
    doc.close()

    chk_doc = fitz.open(pdf_path)
    rects = chk_doc[0].search_for("John Doe")
    chk_doc.close()
    assert len(rects) == 2

    # Target ONLY the second occurrence
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

    out_doc = fitz.open(pdf_path)
    page_text = out_doc[0].get_text()
    out_doc.close()

    assert "John Doe" in page_text
    assert "Elena Rostova" in page_text

# 13. Reusable template preserves source document and allows independent generations
def test_template_reuse_and_independent_generation_values(client, tmp_path):
    doc_path = tmp_path / "reuse_test.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("reuse_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    vars_list = an_resp.json()["variables"]
    target_var = vars_list[0]

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Reusable Template",
        "document_id": doc_id,
        "variables": vars_list
    })
    tpl_id = tpl_resp.json()["id"]

    # Generation 1
    g1 = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {target_var["id"]: "Generation_One_Value"}
    })
    assert g1.status_code == 200

    # Generation 2
    g2 = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {target_var["id"]: "Generation_Two_Value"}
    })
    assert g2.status_code == 200

    assert g1.json()["id"] != g2.json()["id"]

    # Original template is immutable and unchanged
    tpl_check = client.get(f"/api/v1/templates/{tpl_id}").json()
    assert tpl_check["name"] == "Reusable Template"

# 14. Validation detects unexpected changes to protected content
def test_validation_detects_unexpected_content_changes(tmp_path):
    src_docx = tmp_path / "src_tamper.docx"
    d_src = docx.Document()
    d_src.add_paragraph("First paragraph: Replace Me")
    d_src.add_paragraph("Second paragraph: Protected Unchanged Text")
    d_src.save(str(src_docx))

    gen_docx = tmp_path / "gen_tamper.docx"
    d_gen = docx.Document()
    d_gen.add_paragraph("First paragraph: Replacement Applied")
    # Tamper with the unapproved container!
    d_gen.add_paragraph("Second paragraph: CORRUPTED OR TAMPERED TEXT")
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
        excluded_texts=["Protected Unchanged Text"],
        source_path=src_docx
    )

    assert report.status == "failed"
    assert any(i.code in ["UNMODIFIED_CONTENT_ALTERED", "UNAPPROVED_CONTENT_ALTERED", "PROTECTED_CONTENT_ALTERED", "UNMODIFIED_TEXT_MISSING"] for i in report.issues)

# 15. Validation detects missing intended replacement
def test_validation_detects_missing_replacement(tmp_path):
    src_docx = tmp_path / "src_missing.docx"
    d_src = docx.Document()
    d_src.add_paragraph("Salary is $75,000 per year")
    d_src.save(str(src_docx))

    gen_docx = tmp_path / "gen_missing.docx"
    d_gen = docx.Document()
    # Replacement failed to apply
    d_gen.add_paragraph("Salary is $75,000 per year")
    d_gen.save(str(gen_docx))

    intended = [
        {
            "occurrence_id": "occ_salary",
            "container_id": "body/p[0]",
            "original_text": "$75,000",
            "new_text": "$120,000"
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
    assert any(i.code == "REPLACEMENT_LOCATION_MISMATCH" for i in report.issues)

# 16. Format conversion: DOCX -> PDF
def test_docx_to_pdf_conversion(client, tmp_path):
    docx_file = tmp_path / "convert_doc.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("convert_doc.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    vars_list = an_resp.json()["variables"]

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "Convert Template",
        "document_id": doc_id,
        "variables": vars_list,
        "occurrences": an_resp.json()["occurrences"]
    })
    tpl_id = tpl_resp.json()["id"]

    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {vars_list[0]["id"]: "Vikram Patel"},
        "output_format": "pdf"
    })
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["output_format"] == "pdf"
    assert gen_data["status"] == "completed"

    down_resp = client.get(f"/api/v1/generations/{gen_data['id']}/download")
    assert down_resp.status_code == 200
    assert down_resp.content.startswith(b"%PDF-")

# 17. Format rejection: PDF -> DOCX rejected with 400 UNSUPPORTED_FORMAT
def test_pdf_to_docx_rejected(client, tmp_path):
    pdf_path = tmp_path / "src_pdf.pdf"
    create_sample_pdf(pdf_path)
    with open(pdf_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("src_pdf.pdf", f, "application/pdf")})
    doc_id = up_resp.json()["id"]

    an_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    vars_list = an_resp.json()["variables"]

    tpl_resp = client.post("/api/v1/templates", json={
        "name": "PDF Template",
        "document_id": doc_id,
        "variables": vars_list
    })
    tpl_id = tpl_resp.json()["id"]

    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {},
        "output_format": "docx"
    })
    assert gen_resp.status_code == 400
    assert gen_resp.json()["code"] == "UNSUPPORTED_FORMAT"

# 18. Checksum verification fails if source changes
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
        f.write(b"\n#tampered_checksum")

    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={"values": {}})
    assert gen_resp.status_code == 400
    assert gen_resp.json()["code"] == "SOURCE_CHANGED"

# 19. Application restart persistence
def test_restart_persistence(client, tmp_path):
    docx_file = tmp_path / "restart_test.docx"
    create_sample_docx(docx_file)
    with open(docx_file, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("restart_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    client.post(f"/api/v1/documents/{doc_id}/analyze")

    # Clear memory cache
    _analysis_cache.clear()

    # Recovery from database
    res = client.get(f"/api/v1/analysis/{doc_id}")
    assert res.status_code == 200
    assert len(res.json()["variables"]) > 0

# 20. Cascade delete cleans up files and database records
def test_cascade_delete_and_file_cleanup(client, tmp_path):
    doc_path = tmp_path / "cleanup_target.docx"
    create_sample_docx(doc_path)
    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("cleanup_target.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    stored_file = settings.originals_path / f"{doc_id}.docx"
    assert stored_file.exists()

    del_resp = client.delete(f"/api/v1/documents/{doc_id}")
    assert del_resp.status_code == 200
    assert not stored_file.exists()

    get_resp = client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 404

# 21. Complete save -> reload -> generate cycle preserves exact occurrence locators
def test_save_reload_generate_preserves_full_locators(client, tmp_path):
    doc_path = tmp_path / "cycle_test.docx"
    d = docx.Document()
    d.add_paragraph("Agreement between Acme Corporation and Beta Industries LLC.")
    d.add_paragraph("Effective Date: January 15, 2026. Payment: $50,000 upon execution.")
    d.save(str(doc_path))

    with open(doc_path, "rb") as f:
        up_resp = client.post("/api/v1/documents", files={"file": ("cycle_test.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    doc_id = up_resp.json()["id"]

    # 1. Analyze
    ana_resp = client.post(f"/api/v1/documents/{doc_id}/analyze")
    analysis = ana_resp.json()
    assert len(analysis["variables"]) > 0
    assert len(analysis["occurrences"]) > 0

    first_occ = analysis["occurrences"][0]
    orig_char_start = first_occ["source_locator"].get("char_start")
    orig_char_end = first_occ["source_locator"].get("char_end")

    # 2. Save template
    save_resp = client.post("/api/v1/templates", json={
        "name": "Locator Integrity Template",
        "document_id": doc_id,
        "variables": analysis["variables"],
        "occurrences": analysis["occurrences"]
    })
    assert save_resp.status_code == 201
    tpl_id = save_resp.json()["id"]

    # 3. Reload template
    reload_resp = client.get(f"/api/v1/templates/{tpl_id}")
    assert reload_resp.status_code == 200
    reloaded_tpl = reload_resp.json()
    assert len(reloaded_tpl["occurrences"]) > 0

    reloaded_occ = reloaded_tpl["occurrences"][0]
    loc = reloaded_occ["source_locator"]

    # Complete locator must be preserved and restored!
    assert "kind" in loc
    assert "container_id" in loc
    assert loc.get("char_start") == orig_char_start
    assert loc.get("char_end") == orig_char_end

    # 4. Generate from reloaded template
    target_var = reloaded_tpl["variables"][0]
    gen_resp = client.post(f"/api/v1/templates/{tpl_id}/generate", json={
        "values": {target_var["id"]: "Replacement_Value_Success"}
    })
    assert gen_resp.status_code == 200
    job = gen_resp.json()
    assert job["status"] == "completed"
    assert job["validation_report"]["status"] == "passed"
    assert job["validation_report"]["verified_replacements_count"] >= 1

