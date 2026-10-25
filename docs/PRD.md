# Product Requirements Document (PRD)
## AI Document Reuse Platform

### 1. Vision & Core Principles
- **Vision**: Create a private, local-first, AI-assisted document reuse workspace. A user uploads an existing DOCX or PDF, the system analyzes the document, detects likely changeable fields, lets the user approve or reject each field, then generates a new document with only approved changes. The same reviewed template can be reused repeatedly.
- **Core Principle**: Change only what the user approves; preserve all other content and formatting wherever the selected document format and supported feature set allow.
- **Target Audience**: One individual using the application for personal workflows (local-first operation, minimal retention, no multi-tenant complexity).

### 2. Functional Requirements
- **FR-01: Upload and Validate**: Accept DOCX and PDF uploads; enforce file signature, ZIP package integrity, and configurable size/page limits.
- **FR-02: Extract Text and Structure**: Extract paragraphs, tables, runs, headers, and footers (DOCX) and page/bbox text (PDF) with fine-grained source locators.
- **FR-03: Variable Suggestion**: Combine deterministic candidate extraction (regex/patterns for dates, currency, emails, phone numbers, identifiers, names) with AI classification behind an abstraction layer.
- **FR-04: User Review & Editing**: Allow the user to edit labels, types, values, approve or exclude variables, split or merge occurrences, and manually add new variables.
- **FR-05: Source Location Mapping**: Map every approved occurrence to an exact, verifiable source location in the document hierarchy.
- **FR-06: Strict Approved Replacement**: Apply approved replacements only; never perform global blind string replacements.
- **FR-07: Preservation of Unchanged Content**: Preserve unedited paragraphs, formatting runs, tables, headers, footers, and styles.
- **FR-08: Source Preview & Validation Summary**: Provide document preview, change summaries, warnings, and downloadable outputs.
- **FR-09: Reusable Templates**: Save reviewed templates with checksums, allowing repeated generation without re-running analysis.
- **FR-10: Integrity Validation**: Re-parse output after generation, check that intended replacements exist at target locations, verify excluded/protected content remains untouched, and flag conflicts.
- **FR-11: Deletion & Retention**: Provide explicit retention policies and cascade deletion of database records and corresponding files.
- **FR-14: Generation History**: Record every generation run, snapshotting approved values independently from template updates.

### 3. Out of Scope (MVP)
- Autonomous rewriting of entire documents.
- Guaranteed in-place editing of arbitrary scanned PDFs.
- Guaranteed support for Word macros, embedded OLE objects, or complex field codes.
- Batch generation from spreadsheets.
- Public SaaS hosting and team collaboration.
- Optical Character Recognition (OCR) for scanned PDFs (flagged clearly as a known limitation).

### 4. User Journey
1. Upload DOCX or PDF reference document.
2. System validates file signature, size, and structure; extracts text and structural locators.
3. System suggests variable fields (names, dates, amounts, addresses, etc.).
4. User reviews candidates, edits values, approves/excludes fields, splits occurrences, or adds manual variables.
5. User saves the reviewed document as a reusable template.
6. User enters generation values, confirms, and generates output.
7. System validates output against source constraints and provides preview, validation report, and download.
