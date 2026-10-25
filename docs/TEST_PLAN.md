# Test Plan & Acceptance Matrix
## AI Document Reuse Platform

This test plan maps directly to the acceptance criteria defined in Section 13 of the Product Specification.

| ID | Test Case | Target Module | Expected Result |
| :--- | :--- | :--- | :--- |
| **AT-01** | Upload valid DOCX | `services.storage`, `api.documents` | Accepted and stored privately with UUID and SHA256 checksum. |
| **AT-02** | Upload text-based PDF | `services.extraction.pdf`, `api.documents` | Accepted; extractable text and page/bbox mapping returned. |
| **AT-03** | Upload renamed / corrupt file | `services.extraction`, `api.documents` | Rejected with clear error (`UNSUPPORTED_FORMAT` / `INVALID_ARCHIVE`); no partial artifact. |
| **AT-04** | Analyze sample with names/dates/amounts | `services.analysis` | Candidates returned with exact source locators and occurrence IDs. |
| **AT-05** | Edit a detected variable | `api.templates` | Edited label/value appears in review and generation input. |
| **AT-06** | Exclude a variable | `services.replacement` | Original value remains unchanged during generation. |
| **AT-07** | Replace a linked repeated value | `services.replacement.docx` | All and only linked occurrences change to the new value. |
| **AT-08** | Same name refers to two people | `services.mapping`, `services.replacement` | Split occurrence allows changing one instance while keeping the other unchanged. |
| **AT-09** | DOCX with tables, headers, footers | `services.replacement.docx` | Supported structures remain intact and formatting is preserved. |
| **AT-10** | Export supported PDF | `services.generation.pdf` | Generated PDF opens and contains target content changes. |
| **AT-11** | Scanned PDF without OCR | `services.extraction.pdf` | Clear limitation reported (`SCANNED_PDF_NO_TEXT`); no silent false success. |
| **AT-12** | Source changes after analysis | `services.validation` | Checksum mismatch triggers `SOURCE_CHANGED` blocking generation. |
| **AT-13** | Replacement includes punctuation/unicode | `services.replacement` | Special characters (e.g. `&`, `<`, `€`, `—`) handled safely without corruption. |
| **AT-14** | Delete template/document | `api.documents`, `services.storage` | Database records and disk files cleaned according to cascade policy. |
| **AT-15** | Generate twice from saved template | `api.generation` | Independent outputs generated; template and source remain unmodified. |
| **AT-16** | AI provider fails | `services.analysis.ai_adapter` | Fallback gracefully to deterministic extractor; no false success or crash. |
| **AT-17** | Download generated artifact | `api.generation` | File downloaded matches generated SHA256 checksum and is valid. |
| **AT-18** | Inspect application logs | `core.logging` | No sensitive raw document text or replacement values logged. |
| **AT-19** | Document contains prompt injection | `services.analysis` | Content treated strictly as data; no execution or policy override. |
| **AT-20** | Replacement overlaps another edit | `services.mapping` | Conflict detected and rejected (`OVERLAPPING_EDIT`) before modifying output. |

### Test Suites Structure
- `tests/unit/test_docx_extractor.py`: Structural extraction of paragraphs, runs, tables, headers, footers.
- `tests/unit/test_pdf_extractor.py`: Text extraction, bounding boxes, scanned document detection.
- `tests/unit/test_candidate_detector.py`: Regex and pattern candidate detection for entities.
- `tests/unit/test_docx_replacer.py`: Run-level replacement, multi-run spanning phrases, table and header replacement.
- `tests/unit/test_post_validation.py`: Post-generation text extraction and integrity assertion checks.
- `tests/integration/test_document_pipeline.py`: End-to-end integration tests covering AT-01 through AT-20.
