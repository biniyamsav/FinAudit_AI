# FinAudit_AI

**Ask questions about your financial documents. Get answers that point to the page or cell they came from.**

![Python](https://img.shields.io/badge/python-3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Weaviate](https://img.shields.io/badge/Weaviate-Cloud-3FB950)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Deployed on Render](https://img.shields.io/badge/deployed-Render-46E3B7)

**Live demo:** https://finaudit-ai-26q9.onrender.com/
**Interactive API docs:** https://finaudit-ai-26q9.onrender.com/docs

> The demo runs on a free Render instance. It sleeps when idle, so the first load can take about a minute. Workspaces expire automatically. Please do not upload real or sensitive documents.

---

## What it is

FinAudit_AI is a financial document analysis system. You upload a folder's worth of documents (annual reports, contracts, invoices, spreadsheets, scans) into a temporary workspace. The system extracts their content, indexes it, and lets you ask questions in plain language. Every answer is grounded in retrieved evidence and cites where it came from.

It was built around one rule: **in finance, a confident wrong number is worse than no answer.** So the design favors provenance, exact handling of figures, and honest failure over fluent guessing.

## Try it in 30 seconds

1. Open the [live demo](https://finaudit-ai-26q9.onrender.com/).
2. Upload a PDF, Word, Excel, CSV or image file.
3. Wait for the document to show as processed.
4. Ask a question.

Example questions for a supply agreement:

- "What are the payment terms?"
- "When is the first price review?"
- "What does early termination without cause cost?"
- "Who is the governing law?" (a good test: if the document does not say, the answer should say so)

---

## Features

- **Temporary workspaces.** Each workspace has an expiry time (24 hours by default). Uploaded originals are processed and then deleted.
- **Many files per workspace**, each processed independently. One bad file never breaks the others.
- **Wide format support:** PDF (text and tables), Word, Excel, CSV, and images via OCR. Scanned PDF pages are sent to OCR.
- **Safe uploads:** extension allow-list, file signature (magic number) check, size limit, path-traversal protection, and duplicate detection by SHA-256 checksum.
- **Background processing.** Uploads return immediately while extraction and indexing run behind the scenes.
- **Hybrid retrieval:** keyword (sparse) and vector (dense) search, fused and re-ranked, always scoped to a single workspace.
- **Cited answers.** The model answers from retrieved chunks, and each chunk carries its provenance (page, sheet and cell, row, or paragraph).
- **Persistent conversation history** with the chunks each answer cited.
- **Guardrails:** per-workspace document and size limits, rate limits on uploads and chat, extraction timeouts, and page, row and cell caps.
- **Readable failures.** A failed document stores a short error code, never a stack trace or file contents.

---

## How it works

```mermaid
flowchart LR
    U[User / Web UI] -->|upload| API[FastAPI]
    API -->|validate + stream| T[(Temp file)]
    API -->|document + job rows| PG[(PostgreSQL)]
    API -.->|background task| W[Ingestion worker]
    W --> X{Extractor by file type}
    X --> PG
    W -->|chunks + vectors| WV[(Weaviate Cloud)]
    W -->|delete after success| T
```

### Asking a question

```mermaid
sequenceDiagram
    participant U as User
    participant A as API
    participant R as Retrieval
    participant L as LLM (Groq)
    participant D as PostgreSQL
    U->>A: question
    A->>A: rate limit, workspace check
    A->>R: hybrid search (workspace-scoped)
    R-->>A: ranked chunks with provenance
    A->>L: system prompt + evidence + question
    L-->>A: answer
    A->>D: save prompt, answer, cited chunk ids
    A-->>U: answer + citations
```

### Extraction by file type

| Type | Method | Provenance kept |
|---|---|---|
| PDF text | `pypdf` | page number |
| PDF tables | `pdfplumber` | page number, rows of cell strings |
| Scanned PDF pages, images | RapidOCR (ONNX, runs locally) | text lines with confidence scores |
| `.xlsx` | `openpyxl` | sheet, cell reference, number format |
| `.xls` | `xlrd` | sheet, cell reference |
| `.csv` | `csv` with delimiter sniffing, BOM handling | row number |
| `.docx` | `python-docx` | paragraph index, tables |

Each extractor returns a validated Pydantic model with a `schema_version`, stored as JSONB.

### Failure codes

When a document fails, the ingestion job stores one of a small set of codes:

| Code | Meaning |
|---|---|
| `unsupported_type` | no extractor for this file type |
| `page_limit_exceeded` | more pages than `EXTRACTION_MAX_PAGES` |
| `no_text_found` | OCR read nothing from an image |
| `ocr_failed` | file could not be read as an image |
| `extraction_failed` | unexpected extraction error |
| `vector_store_failed` | chunks could not be indexed in Weaviate |

---

## Accuracy principles

These are the design rules the rest of the code follows.

1. **Retrieval is not calculation.** Vector search finds the right passage. It is never trusted to do arithmetic. The goal is for figures to be computed by deterministic code with exact decimals, not by a language model guessing digits.
2. **Numbers stay as text.** Monetary values and figures are stored as strings exactly as written in the source. They are never converted to floating point, which would corrupt money.
3. **Provenance on everything.** Every extracted piece records where it came from, so an answer can be checked against the source.
4. **Say "not found."** The model is instructed to answer only from the retrieved evidence. A question the document does not answer should be reported as unanswered.
5. **Low-confidence data is labeled.** OCR output carries a confidence score and is not presented as certain.
6. **Fail visibly.** A document that cannot be processed is marked `failed` with a reason, never silently returned empty.
7. **Workspace isolation.** Retrieval is filtered by workspace, and citations can only point to documents in the asking workspace.

---

## Tech stack

| Layer | Choice |
|---|---|
| API | Python 3.11, FastAPI, Pydantic, pydantic-settings |
| Relational data | PostgreSQL, SQLAlchemy 2.0, Psycopg 3, Alembic migrations |
| Vector search | Weaviate Cloud (HFresh index), `weaviate-client` 4.22+ |
| LLM | Groq through the OpenAI-compatible client (`openai/gpt-oss-120b`) |
| OCR | RapidOCR on ONNX Runtime, runs locally, no external API |
| Documents | pypdf, pdfplumber, pypdfium2, openpyxl, xlrd, python-docx, Pillow |
| Frontend | Static HTML, CSS and JavaScript served by the API |
| Tests | pytest, httpx test client |
| Deployment | Docker on Render, Render PostgreSQL |

---

## API

Full interactive documentation lives at [`/docs`](https://finaudit-ai-26q9.onrender.com/docs). The main endpoints:

| Method | Path | Purpose | Notes |
|---|---|---|---|
| `GET` | `/api/v1/health` | liveness check | |
| `GET` | `/api/v1/health/status` | PostgreSQL, Weaviate and Groq connectivity | |
| `POST` | `/api/v1/workspaces` | create a workspace | `201` with id, status, expiry |
| `POST` | `/api/v1/workspaces/{workspace_id}/documents` | upload a document | `201` new, `200` duplicate (returns the existing document), `400` empty, `413` too large, `415` bad type or signature |
| `GET` | `/api/v1/workspaces/{workspace_id}/documents/{document_id}/content` | read extracted content | `409` while the document is not `ready` |
| `POST` | `/api/v1/workspaces/{workspace_id}/chat` | ask a question | returns the answer, its citations and the stored message id; rate limited |

Uploading the same file twice into one workspace is idempotent. A race between two simultaneous identical uploads is handled by the database constraint.

---

## Data model

```mermaid
erDiagram
    USERS ||--o{ WORKSPACES : owns
    WORKSPACES ||--o{ DOCUMENTS : contains
    WORKSPACES ||--o{ CONVERSATION_MESSAGES : has
    DOCUMENTS ||--o{ INGESTION_JOBS : "processed by"
    DOCUMENTS ||--|| EXTRACTED_CONTENT : yields
```

| Table | Purpose |
|---|---|
| `users` | accounts (the schema is ready, login is not built yet, so workspaces are anonymous) |
| `workspaces` | temporary sessions with status (`active`, `expired`, `deleting`) and expiry |
| `documents` | file metadata and status (`uploaded`, `processing`, `ready`, `failed`); unique per workspace and checksum |
| `ingestion_jobs` | one row per processing attempt: status, attempt count, short error code, timestamps |
| `extracted_content` | one JSONB record per document |
| `conversation_messages` | prompts, answers and cited chunk ids |

Deleting a workspace cascades to its documents, jobs and extracted content in PostgreSQL. Status columns are protected by `CHECK` constraints, and foreign keys are indexed.

Original files are never stored in the database. Weaviate holds the searchable chunks and embeddings, each tagged with `workspace_id` and `document_id`.

---

## Security and privacy

- **Originals are temporary.** Uploads are written to a temp folder, processed, and deleted after successful extraction.
- **Client filenames never control paths.** Stored files use generated UUIDs, and the filename is reduced to its last component.
- **Content is verified, not trusted.** The file's leading bytes must match its extension, and the client-supplied MIME type is treated as informational only.
- **No secrets in the repo.** All credentials come from environment variables, and `.env` is git-ignored.
- **Safe error output.** Clients get generic JSON errors. Stack traces go to server logs only.
- **Abuse limits.** Upload and chat rate limits, per-workspace document and byte quotas, and extraction timeouts.
- **Anonymous by design for now.** There is no authentication yet. See the limitations below.

---

## Running locally

Requirements: Python 3.11, PostgreSQL, and a Weaviate server. The easiest Weaviate is a free cluster on [Weaviate Cloud](https://console.weaviate.cloud). `weaviate-client` 4.22+ needs a server version 1.27 or newer, and Weaviate Cloud clusters here accept only the `hfresh` vector index, which the code requests.

```powershell
git clone https://github.com/biniyamsav/FinAudit_AI.git
cd FinAudit_AI
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env`: set `DATABASE_URL` (for example `postgresql+psycopg://USER:PASSWORD@localhost:5432/financial_audit_db`), `WEAVIATE_URL`, and `WEAVIATE_API_KEY`. Leave `LLM_PROVIDER_MODE=mock` to run without a Groq key, or set it to `external` with `LLM_API_KEY`.

Create the database, apply migrations, and start the server:

```powershell
python -m alembic upgrade head
python -m uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 for the UI and http://127.0.0.1:8000/docs for the API.

> On locked-down Windows machines the `pip` and `alembic` launchers can be blocked. Always call them through Python: `python -m pip`, `python -m alembic`.

## Tests

Tests run against a separate database named `audit_test`, which is migrated automatically at the start of each run. Create it once:

```sql
CREATE DATABASE audit_test;
```

```powershell
python -m pip install pytest pytest-asyncio httpx xlwt
python -m pytest -q
```

The suite covers the upload flow, validation and path traversal, duplicate handling, every extractor, the ingestion worker, limits, error safety, retrieval, and the chat API. Tests that touch Weaviate need `WEAVIATE_URL` and `WEAVIATE_API_KEY` to point at a reachable cluster.

---

## Deployment

The app ships as a Docker image (`Dockerfile`, `start.sh`) and is described by `render.yaml`. On start, `start.sh` applies migrations and launches Uvicorn on the port Render provides.

Required environment variables on Render:

| Variable | Value |
|---|---|
| `ENVIRONMENT` | `production` |
| `LLM_PROVIDER_MODE` | `external` |
| `DATABASE_URL` | the Render database's internal URL |
| `LLM_API_KEY` | Groq API key |
| `WEAVIATE_URL` | Weaviate Cloud REST endpoint |
| `WEAVIATE_API_KEY` | Weaviate Cloud API key |

In production the app refuses to start without the database, LLM and Weaviate settings. The database URL is normalized to the `postgresql+psycopg://` driver form, and the Weaviate URL is normalized to a clean `https://host` address.

## Configuration

Every setting is an environment variable named after the field in `app/core/config.py`.

| Variable | Default | Meaning |
|---|---|---|
| `ENVIRONMENT` | `development` | `development`, `testing` or `production` |
| `DATABASE_URL` | none | PostgreSQL connection string |
| `TEMP_UPLOAD_DIR` | `./temporary_uploads` | where originals live until extraction finishes |
| `WORKSPACE_TTL_HOURS` | `24` | workspace lifetime |
| `MAX_DOCUMENTS_PER_WORKSPACE` | `20` | document quota |
| `MAX_WORKSPACE_BYTES` | `200000000` | byte quota per workspace |
| `UPLOAD_RATE_LIMIT_PER_MINUTE` | `20` | upload rate limit |
| `CHAT_RATE_LIMIT_PER_MINUTE` | `10` | chat rate limit |
| `EXTRACTION_TIMEOUT_SECONDS` | `300` | per-document extraction timeout |
| `EXTRACTION_MAX_PAGES` | `200` | PDF page cap |
| `EXTRACTION_MAX_ROWS` | `100000` | CSV row cap |
| `EXTRACTION_MAX_CELLS` | `500000` | Excel cell cap |
| `EXTRACTION_MAX_OCR_PAGES` | `30` | OCR page cap per document |
| `PROCESSING_STALE_MINUTES` | `15` | minutes before a document stuck in `processing` counts as stale |
| `CLEANUP_INTERVAL_MINUTES` | `30` | interval for expiry cleanup |
| `CORS_ORIGINS` | localhost origins | allowed browser origins |
| `LLM_PROVIDER_MODE` | `mock` | `mock` (offline, for tests) or `external` (Groq) |
| `LLM_API_KEY` | none | Groq API key |
| `WEAVIATE_URL` | none | Weaviate Cloud endpoint; when unset, a local server is used |
| `WEAVIATE_API_KEY` | none | Weaviate Cloud key |
| `WEAVIATE_HOST`, `WEAVIATE_HTTP_PORT`, `WEAVIATE_GRPC_PORT` | `localhost`, `8080`, `50051` | local Weaviate connection |
| `LOG_LEVEL` | `INFO` | logging level |

---

## Project structure

```
app/
  api/routes/        health, workspaces, documents, chat endpoints
  core/              settings (config.py), logging
  db/                SQLAlchemy base, models and lazy session factory
  ingestion/         one extractor per file type, shared error type
  retrieval/         embeddings, dense and sparse search, fusion, reranking, context building
  llm/               provider interface and the Groq provider
  workers/           background ingestion worker
migrations/          Alembic migrations
ui/                  static web interface (HTML, CSS, JavaScript)
tests/               pytest suite
Dockerfile, start.sh, render.yaml
```

---

## Engineering notes

Decisions and problems solved while building this:

- **Originals are never kept.** Uploads stream to a temp path built from generated IDs, so no `storage_key` column is needed. The file is deleted only after the extracted content is committed. A failed document keeps its temp file so it can be retried.
- **Alembic with a hand-written initial migration.** The schema, including constraints and indexes, is explicit SQL, and the migration was verified on an empty database.
- **SQLAlchemy is pinned below 2.1.** On a Windows machine with Application Control, the compiled extension in SQLAlchemy 2.1 was blocked from loading. Pinning to 2.0 keeps setup reproducible. For the same reason, tools are invoked as `python -m`.
- **JSONB rejects NUL characters.** Extracted text is cleaned of `\x00` before saving, so one odd PDF cannot crash a save.
- **`openpyxl` refuses files without an extension.** Temp files have none, so workbooks are opened through a file handle.
- **Concurrent duplicate uploads.** Two identical simultaneous uploads race past the "already exists" check. The unique constraint catches the loser, and the API returns the existing document.
- **Weaviate Cloud restricts the vector index type.** A new cluster accepted only `hfresh`, so the collection is created explicitly with that index and self-provided vectors, and the client was upgraded to match.
- **Model churn.** The default Groq model disappeared from the account's available list. The real failure was hidden behind a generic message, so errors are now logged with their cause while clients still see a safe message.
- **Embeddings are deliberately simple.** Vectors are a deterministic hashed bag of words. They work offline with no API key, but they are lexical, not semantic. Keyword search, fusion and reranking compensate. Swapping in a learned embedding model means changing one function, `embed_text`.
- **Indexing failures are surfaced.** Weaviate's batch API does not raise when objects are rejected, so rejected chunks are counted and the document is failed instead of being marked ready while unsearchable.

---

## Known limitations

- **No authentication.** Workspaces are anonymous. Anyone with a workspace id can use it until it expires.
- **Charts are not interpreted.** Values inside chart images are not extracted as data. Text inside images may be picked up by OCR, with a confidence score.
- **Tables from complex layouts** can come out imperfect, since PDF table extraction is heuristic.
- **Legacy `.xls` support is lightly tested.**
- **Arithmetic is not yet fully deterministic.** Figures are preserved exactly, but a dedicated `Decimal` calculation layer that the answer path must use is still ahead on the roadmap. Treat computed values in answers as needing verification against the cited source.
- **Retrieval quality is limited by the lexical embeddings** until a learned embedding model is added.
- **Background tasks run inside the web process.** A restart during extraction interrupts it.
- **The hosted demo uses free tiers.** The instance sleeps when idle, local disk does not survive a restart, and the free database has a limited lifetime.

## Roadmap

- Deterministic calculation layer using `Decimal`, wired into the answer path, with calculation steps shown in answers
- Chart and figure extraction with a vision model, stored with confidence labels
- A learned embedding model for true semantic search
- Authentication and per-user workspaces
- A durable job queue in place of in-process background tasks
- Evaluation set for answer accuracy and citation correctness, run in CI

---

## Author

Built by **Biniyam Worku Desta**, third-year Computer Science student at Addis Ababa University.

Repository: https://github.com/biniyamsav/FinAudit_AI