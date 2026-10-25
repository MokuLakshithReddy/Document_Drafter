# AI Document Reuse Platform

## Overview
A private, local-first, AI-assisted document reuse workspace. A user uploads an existing DOCX or PDF, the system analyzes the document, detects likely changeable fields (names, dates, amounts, roles, addresses, IDs), lets the user approve/reject/edit fields and inspect occurrences, then generates a new document with only approved changes while preserving all unchanged content and formatting.

## Core Principle
**Change only what the user approves; preserve all other content and formatting wherever the selected document format and supported feature set allow.**

## Architecture & Technology Stack
- **Frontend**: React 18 + TypeScript + Vite + Tailwind/Modern Clean CSS + Lucide Icons
- **Backend API**: Python FastAPI + Pydantic v2 + Uvicorn (bound to `127.0.0.1`)
- **Database**: SQLite with SQLAlchemy ORM
- **DOCX Processing**: `python-docx` with run-level multi-run phrase matching and structural integrity verification
- **PDF Processing**: `PyMuPDF` (`fitz`) for text extraction, page and bounding-box mapping, and ReportLab / PyMuPDF PDF export
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
   - Validates file signatures, file sizes, page limits, and ZIP package safety against ZIP bombs.
   - Detects format: DOCX, text-based PDF, or scanned PDF without text (flags scanned PDF clearly).
2. **Text & Structural Extraction**:
   - DOCX: paragraphs, runs, tables, headers, footers with granular source locators.
   - PDF: text extraction with page numbers and coordinate bounding boxes.
3. **Variable Detection & AI Adapter**:
   - Deterministic candidate extraction (regex & NER patterns for dates, currency, emails, phone numbers, IDs, person names, organizations).
   - AI enhancement interface with strict JSON schema validation.
   - Fallback mode works 100% offline without cloud AI.
4. **Interactive Review**:
   - View document preview with highlighted occurrences.
   - Edit label, type, and replacement values.
   - Approve, exclude, split occurrences, or add custom fields.
   - Overlap and conflict prevention.
5. **Deterministic DOCX & PDF Generation**:
   - Edits are applied to working copies only; original files are immutable.
   - Multi-run phrase replacement preserves font styles and bold/italic runs.
   - Table, header, and footer replacements.
6. **Post-Generation Validation**:
   - Re-extracts generated file content to ensure approved changes took effect and protected content was untouched.
   - Generates an automated validation report before download.
7. **Template Library & History**:
   - Save reviewed document as a reusable template.
   - Generate multiple outputs with independent variable values.
   - Configurable file retention and cascade deletion.

---

## Known Limitations
- **PDF In-place Editing**: In-place replacement of complex arbitrary PDFs with preserved font vectors is unsupported by design in MVP; a supported PDF regeneration path and DOCX-to-PDF/styled PDF export is provided.
- **Scanned PDFs**: Scanned image PDFs without text layer require OCR which is flagged as an explicit limitation in this MVP.
- **Complex Word Features**: Macros, active content controls, embedded OLE objects, and complex field codes are rejected or ignored to preserve security and stability.

---

## Security & Privacy
- Localhost binding (`127.0.0.1`) only.
- Private storage outside public web directory.
- No raw sensitive document text logged in server logs.
- Safe path resolution defending against directory traversal.
