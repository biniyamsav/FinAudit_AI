# FinAudit_AI

Financial document analysis and audit system. Users upload financial documents into temporary workspaces; the system extracts their content (text, tables, spreadsheets, scanned pages via OCR) and stores it with provenance. Search, exact Decimal calculations and cited question answering are planned but not yet implemented.

Status: ingestion and extraction are built. Semantic search, exact calculations and question answering are not yet.

## Features today

- Workspaces with expiry time.
- Multi-file upload per workspace.
- Validation by extension, file signature and size (25 MB).
- Duplicate detection by sha256 checksum.
- Background extraction.
- PDF text and tables.
- Excel, CSV and Word.
- OCR for images (rapidocr-onnxruntime) with confidence scores.
- Short error codes on failures.
- Temporary originals deleted after successful extraction.

## Architecture

Flow: upload -> temp file -> background worker -> extractor chosen by file extension -> JSONB in PostgreSQL -> temp file deleted.

PostgreSQL holds relational data and extracted content. Weaviate (planned) will hold chunks and embeddings.

Design rules: money and numbers stored as strings; provenance on every extracted piece; calculations use Decimal, never an LLM.

## Database

Tables:
- users: user accounts.
- workspaces: temporary workspaces with expiry.
- documents: uploaded file metadata.
- ingestion_jobs: extraction job state.
- extracted_content: extracted JSONB content.
- conversation_messages: stored chat exchanges.

Cascade delete: deleting a workspace cascades to documents, jobs and extracted content.

## API endpoints

| Method | Path | Purpose | Status codes |
|---|---|---|---|
| GET | /api/v1/health | liveness | 200 |
| POST | /api/v1/workspaces | create workspace | 201 |
| POST | /api/v1/workspaces/{workspace_id}/documents | upload document | 201, 200 (duplicate), 4xx |
| GET | /api/v1/workspaces/{workspace_id}/documents/{document_id}/content | get extracted content | 200, 404, 409 |

Duplicate upload returns 200 with the existing document.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# set DATABASE_URL in .env
# create database financial_audit_db
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Note: on locked-down Windows machines `pip` and `alembic` launchers can be blocked, so always use `python -m`.

## Running tests

Tests use a separate database named `audit_test` which must be created once (`CREATE DATABASE audit_test;`). conftest migrates it automatically.

```powershell
python -m pytest -q
```

## Configuration

See .env.example for all variables: DATABASE_URL, TEMP_UPLOAD_DIR, WORKSPACE_TTL_HOURS, PROCESSING_STALE_MINUTES, EXTRACTION_MAX_PAGES, etc.

## Project structure

- app/ - application code (implemented)
- tests/ - tests (implemented)
- migrations/ - Alembic migrations (implemented)
- ui/ - web UI (placeholder)
- docs/ - decisions and ADRs

## Known limitations

- Legacy .xls untested.
- Scanned PDF pages flagged needs_ocr but not yet OCR'd.
- Charts not extracted.
- Background tasks run in-process and are lost on restart.
- No authentication yet (workspaces are anonymous).
- Expiry cleanup job not built.
- Free-tier hosting caveats.

## Roadmap

- Scanned-PDF OCR.
- Chart extraction with a vision model.
- Chunking and Weaviate search.
- Decimal calculation module.
- Cited question answering.
- Workspace expiry cleanup.
- Authentication.
- Deployment.

## Decisions

See docs/decisions.md.