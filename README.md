# FinAudit_AI

FinAudit_AI is a financial document audit engine that extracts, indexes, and answers questions over uploaded financial documents. It exposes a FastAPI HTTP API backed by PostgreSQL and Weaviate.

## Architecture

- PostgreSQL stores relational data and extracted content as JSONB.
- Weaviate stores document chunks and their embeddings.
- Embeddings are computed locally with a hashed embedder.
- Groq is used to generate answers.

## Setup

1. Copy `.env.example` to `.env` and fill in values.
2. Start services: `docker compose up -d`
3. Install dependencies: `python -m pip install -r requirements.txt` (or per `pyproject.toml`).
4. Create the `audit_test` database (used by the test suite).
5. Run migrations: `python -m alembic upgrade head`
6. Start the app: `python -m uvicorn app.main:app --port 8000`
7. Run tests: `python -m pytest -q`

## API routes

- `GET /api/v1/health` — health check.
  - `curl http://localhost:8000/api/v1/health`
- `GET /api/v1/status` — status.
  - `curl http://localhost:8000/api/v1/status`
- `POST /api/v1/workspaces` — create a workspace.
  - `curl -X POST http://localhost:8000/api/v1/workspaces`
- `POST /api/v1/workspaces/{workspace_id}/documents` — upload a document.
  - `curl -X POST -F "file=@a.pdf" http://localhost:8000/api/v1/workspaces/{workspace_id}/documents`
- `GET /api/v1/workspaces/{workspace_id}/documents/{document_id}/content` — get extracted content.
  - `curl http://localhost:8000/api/v1/workspaces/{workspace_id}/documents/{document_id}/content`
- `POST /api/v1/workspaces/{workspace_id}/documents/{document_id}/retry` — retry a failed document.
  - `curl -X POST http://localhost:8000/api/v1/workspaces/{workspace_id}/documents/{document_id}/retry`
- `POST /api/v1/workspaces/{workspace_id}/chat` — chat over documents.
  - `curl -X POST -H "Content-Type: application/json" -d '{"question":"..."}' http://localhost:8000/api/v1/workspaces/{workspace_id}/chat`

## Privacy

Excerpts of uploaded documents are sent to Groq to generate answers.

## Known limitations

- No authentication; the workspace id is the only credential.
- No Decimal calculation module; totals come from the LLM and must be verified against the source.
- No chart extraction.
- OCR figures may be misread.
- Scanned tables lose their structure.
- Rate limiter is per-process only.
- Background tasks are lost on restart (stale-document recovery exists).
- Extraction timeout stops waiting but cannot kill a hung thread.
- Never tested on real annual reports.

## Implemented hardening

- Workspace expiry cleanup.
- Stale-processing recovery.
- Manual retry endpoint.
- Upload limits.
- Safe 500 responses.
