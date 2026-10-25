# System Architecture
## AI Document Reuse Platform

### 1. High-Level Architecture

```
+-------------------------------------------------------------+
|                  Frontend (React + Vite)                    |
|  - Upload / Analysis / Review UI / Generation / Settings   |
+------------------------------+------------------------------+
                               | REST API (HTTP / JSON)
+------------------------------v------------------------------+
|                   Backend (FastAPI)                         |
|  - Routers: documents, analysis, templates, generation      |
|  - Core: Config, Security, StorageManager                   |
+-------+--------------+-------------------+------------------+
        |              |                   |
+-------v------+ +-----v-----------+ +-----v-----------+
| DOCX Adapter | |  PDF Adapter    | |  AI Adapter     |
| (python-docx)| |  (PyMuPDF)      | | (Provider-Ag.)  |
+-------+------+ +-----+-----------+ +-----+-----------+
        |              |                   |
+-------v--------------v-------------------v------------------+
|                   Data & Persistence Layer                  |
|  - SQLite DB (SQLAlchemy) for metadata & generation records |
|  - File Storage: storage/{originals, working, generated}    |
+-------------------------------------------------------------+
```

### 2. Module Boundaries & Responsibilities

- **`app/core/config.py`**: Centralized configuration management with Pydantic settings. Enforces 127.0.0.1 binding, storage paths, file limits, and provider choice.
- **`app/services/storage/`**: Safe file persistence, random GUID-based physical filenames, path traversal sanitization, and cleanup routines.
- **`app/services/extraction/`**:
  - `docx_extractor.py`: Parses paragraphs, runs, tables (cells/rows), headers, and footers. Assigns unique hierarchical source locators (e.g., `body/p[3]/run[1]`, `table[0]/r[1]/c[2]/p[0]/run[0]`, `header[0]/p[0]`).
  - `pdf_extractor.py`: Extracts text blocks with page indices, bounding boxes (`[x0, y0, x1, y1]`), and detects scanned non-text pages.
- **`app/services/analysis/`**:
  - `candidate_detector.py`: Deterministic entity extractor using regex and pattern rules for dates, currency, emails, phone numbers, identifiers, and common naming conventions.
  - `ai_adapter.py`: Abstract interface `AIAdapter` with implementations:
    - `DeterministicAIAdapter`: Offline fallback ensuring full functionality without external API keys.
    - `GeminiAIAdapter` / `OpenAIAdapter`: Semantic classification into structured schema without file modification privileges.
- **`app/services/mapping/`**:
  - Validates and binds candidates to exact source locators. Prevents overlapping replacement ranges.
- **`app/services/replacement/`**:
  - `docx_replacer.py`: Performs exact run-level replacement. When phrases span across multiple runs, safely updates text across runs while preserving character formatting styles.
  - `pdf_replacer.py`: Handles supported PDF generation routes (e.g. ReportLab or PyMuPDF re-rendering with explicit limitations).
- **`app/services/validation/`**:
  - Pre-generation verification: checks required fields, version match, and non-overlapping edits.
  - Post-generation verification: re-extracts text from generated document, verifies replaced tokens, and confirms protected text has zero unauthorized alterations.
- **`app/db/`**:
  - Database models (`Document`, `Template`, `TemplateVariable`, `VariableOccurrence`, `GenerationJob`, `GenerationValue`, `GeneratedDocument`, `AuditEvent`).

### 3. Data Flow
1. **Upload**: User uploads file -> Validated -> Saved to `storage/originals/<uuid>.<ext>` -> Document record created (`status=UPLOADED`).
2. **Analysis**: Extract text & structural locators -> Generate deterministic candidates -> (Optional) AI enhancement -> Candidates saved with unique occurrence IDs -> Return candidates for review.
3. **Template Creation**: User reviews, edits, approves/excludes variables -> Template record created with frozen source checksum.
4. **Generation**: User inputs target values -> Working copy created in `storage/working/` -> Deterministic replacement applied -> Post-generation validation re-parses output -> Generated document saved in `storage/generated/` -> Download enabled if validation passes.
