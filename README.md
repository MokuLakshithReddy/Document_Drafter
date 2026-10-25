# AI Document Reuse Platform

## Overview
A private, local-first document reuse workspace. A user uploads an existing DOCX or text-based PDF, the system extracts structure and detects likely changeable fields (names, dates, amounts, roles, addresses, IDs), lets the user enter replacement values, and generates a new document where only fields with non-empty replacement values are modified while leaving all other document content completely unchanged.

## Core Principle
**If the user enters a non-empty new value, replace the corresponding original value. If the user leaves the field blank or omits it, leave the original document content unchanged.**

## Architecture & Technology Stack
- **Frontend**: React 18 + TypeScript + Vite + Tailwind/Modern CSS + Lucide Icons
- **Backend API**: Python FastAPI + Pydantic v2 + Uvicorn (bound to `127.0.0.1`)
- **Database**: SQLite with SQLAlchemy ORM (auto-migrating schema on startup)
- **DOCX Processing**: `python-docx` with run-level multi-run phrase matching and structural integrity verification
- **PDF Processing**: `PyMuPDF` (`fitz`) for text extraction, exact bounding-box targeting, and span-level typography/color preservation
- **AI Adapter**: Provider-independent structured output interface supporting Gemini / OpenAI / Ollama, with fully deterministic heuristic fallback when no API key is provided
- **Storage**: Local-first private directory structure:
  - `storage/originals/`
  - `storage/working/`
  - `storage/generated/`
  - `storage/temp/`

---

## Prerequisites
- **Node.js**: v18+ (tested with v24)
- **npm**: v9+ (or `npm.cmd` on Windows)
- **Python**: 3.10+ (tested with 3.12)

---

## Installation & Setup on Windows

### 1. Environment Configuration
Copy the example environment file:
```powershell
Copy-Item .env.example .env
```
Default settings run in local deterministic mode without needing an external API key. You may optionally supply a Gemini or OpenAI key in `.env`:
```ini
AI_PROVIDER=deterministic # or 'gemini', 'openai'
GEMINI_API_KEY=your_gemini_api_key_here
HOST=127.0.0.1
PORT=8000
MAX_UPLOAD_SIZE_MB=25
MAX_PAGE_LIMIT=100
STORAGE_DIR=./storage
```

### 2. Backend Setup
Navigate to the `backend` directory:
```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### 3. Frontend Setup
Navigate to the `frontend` directory:
```powershell
cd frontend
npm.cmd install
```

---

## Running the Application

### Start Backend:
```powershell
cd backend
.\venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
API runs on `http://127.0.0.1:8000` with Swagger docs available at `http://127.0.0.1:8000/docs`.

### Start Frontend:
```powershell
cd frontend
npm.cmd run dev
```
Open `http://localhost:5173` in your browser.

---

## Running Tests

### Backend Unit & Integration Tests:
```powershell
cd backend
.\venv\Scripts\Activate.ps1
pytest -v
```

### Frontend Type-Check & Build:
```powershell
cd frontend
npm.cmd run build
```

---

## Features & Workflows

1. **Upload & Format Detection**:
   - Validates file signatures, file sizes (up to 25MB), page limits (up to 100 pages), and ZIP bomb safety.
   - Robust binary signature detection for DOCX and text-based PDF. Flags scanned image-only PDFs clearly.

2. **Text & Structural Extraction**:
   - DOCX: paragraphs, runs, tables, headers, footers with granular source locators.
   - PDF: text extraction with page numbers, exact coordinate bounding boxes, and span font metrics.

3. **Variable Detection & Heuristic/AI Adapter**:
   - Deterministic candidate extraction (regex & NER patterns for dates, currency, emails, phone numbers, IDs, person names, organizations).
   - AI enhancement interface with strict JSON schema validation. Works 100% offline without cloud AI.

4. **Simplified Replacement Review**:
   - Review each detected variable's label, original value, and optional new value.
   - **Simple rule**: non-empty input replaces original value; blank/omitted leaves original document content unchanged.
   - Exact occurrence locators (container ID, character start/end, run index, page, bounding box) are preserved across template save, reload, and generation cycles.

5. **Exact Occurrence Replacement**:
   - DOCX: Multi-run phrase replacement preserves formatting runs, bold/italic attributes, and font styles across split XML nodes.
   - PDF: Strict coordinate targeting. Redaction only targets the verified bounding box on the specified page, extracting font size, family, and color from the original text span. Missing or ambiguous locations fail closed rather than guessing.

6. **Strict Post-Generation Validation**:
   - Re-extracts generated document and baseline source document.
   - Verifies each replacement occurred at the intended container and consumed the original text.
   - Fails closed on missing source containers, unintended container alterations, or missing unmodified original text.
   - Generates an automated validation report before download.

7. **Template Library & Multi-Generation**:
   - Save documents as reusable templates with full occurrence locators.
   - Start each generation with clean blank inputs, with optional button to load saved defaults.
   - Cascade delete cleanly cleans up database records and disk storage.

---

## Conversion & Layout Fidelity

- **DOCX-to-PDF Conversion**:
  - If headless LibreOffice (`soffice`) is installed on the host system, the platform utilizes it for native 1:1 print layout fidelity.
  - In environments without LibreOffice, the platform falls back to a structured ReportLab flowable engine that preserves document headers, footers, paragraphs, styling runs, and tables. Validation reports flag a `LAYOUT_APPROXIMATION` notice to indicate that custom Word vector geometries and exact print line-wraps are approximated.
  - To guarantee 100% native layout fidelity, users are advised to output in Word (.docx) format or install LibreOffice.
- **PDF In-place Editing**: In-place replacement uses exact bounding-box redaction and span-level font/color preservation. Ambiguous or non-intersecting text occurrences fail closed.
- **Scanned PDFs**: Scanned image PDFs without OCR text layer are flagged upon upload as requiring OCR before processing.

---

## Security & Privacy
- Localhost binding (`127.0.0.1`) only by default.
- Private storage outside public web directory.
- No sensitive document text logged in server audit trails.
- Safe path resolution defending against directory traversal.
