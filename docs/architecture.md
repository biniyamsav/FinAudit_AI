# FinAudit_AI — Architecture & System Design

**Project:** Agentic Financial Knowledge Graph & Compliance Audit Engine  
**Document:** `docs/architecture.md`  
**Version:** 1.1  
**Status:** Architectural specification  
**Last updated:** October 21, 2026

> This document defines the intended architecture of FinAudit_AI. It is the architectural reference for implementation, not evidence that any component is already implemented, tested, secure, or production-ready. Material changes must be documented and reviewed explicitly.

---

## 1. Architectural Principles

### 1.1 Evidence Before Eloquence

Every material factual claim in a generated answer must be supported by retrievable evidence from the authorized document collection.

The system must validate citations against actual source records. If evidence is missing, unreliable, contradictory, or insufficient, it must qualify its answer or abstain rather than inventing facts.

### 1.2 One Engine, Two Deployment Modes

The hosted cloud edition and private self-hosted edition share the same core engine, business rules, data contracts, retrieval behavior, financial calculations, graph logic, and answer schema.

Deployment-specific differences belong in configuration, storage adapters, authentication, interfaces, and infrastructure.

### 1.3 Deterministic Financial Mathematics

Financial calculations must be performed by explicit, tested Python functions.

An LLM may help identify a relevant calculation or explain its result, but it must not independently determine the final arithmetic result. Calculation inputs must be validated for units, periods, metric definitions, accounting basis, and provenance.

### 1.4 Privacy Is an Architectural Property

Original documents, extracted text, tables, embeddings, graph facts, prompts, queries, answers, caches, logs, and backups are potentially sensitive.

Access controls, tenant boundaries, retention policies, and deletion requirements must apply to both original data and derived data.

### 1.5 Incremental, Testable Engineering

Each component must be implemented in a small, independently testable phase.

Before implementation, inspect the existing repository and define the next acceptance criteria. After implementation, run the relevant tests, inspect the results, and update `docs/PROJECT_STATUS.md`.

### 1.6 Explicit Decisions and Honest Limitations

Do not add infrastructure without a justified requirement. Do not treat model confidence as proof, graph relationships as verified facts without provenance, or successful parsing as proof of extraction quality.

Unresolved technology choices remain open until evaluated and explicitly decided.

---

## 2. Product Definition

FinAudit_AI is a source-grounded financial document intelligence and audit-assistance platform.

Users upload financial reports, filings, financial statements, tables, footnotes, and other authorized documents. They ask questions in natural language, and the system retrieves relevant evidence, identifies financial relationships, validates comparability, performs deterministic calculations, and generates answers with citations and limitations.

The system is designed to support:

- Financial metric research across reporting periods.
- Comparisons between companies and business segments.
- Financial statement and footnote investigation.
- Identification of potential discrepancies between reported values.
- Analysis of management statements alongside risk disclosures.
- Reproducible calculations supported by source evidence.
- Investigation of relationships between facts, entities, periods, and documents.

FinAudit_AI is an audit-assistance and research tool. It is not a certified auditor, legal opinion, investment adviser, or guarantee of regulatory compliance. Human judgment remains necessary for consequential decisions.

---

## 3. Deployment Architecture

### 3.1 Hosted Cloud Edition

The hosted edition provides a web-accessible application for authenticated users and organizations.

**Baseline infrastructure:**

- FastAPI for the backend API.
- A dedicated web interface for the hosted user experience.
- Managed PostgreSQL with pgvector.
- Private S3-compatible object storage for original documents.
- A background worker for document ingestion.
- Neo4j when the graph implementation phase begins.
- A configured external LLM provider through a provider-independent interface.

Render is the initial candidate for hosting the application, subject to plan, region, resource, and operational requirements.

The hosted edition must enforce server-side authentication, organization membership, document permissions, tenant-aware retrieval, secure object access, retention, and deletion.

Original files must not depend on an ephemeral application filesystem for durable storage.

### 3.2 Private Self-Hosted Edition

The private edition is deployed on company-controlled infrastructure using Docker Compose.

The initial user interface is Streamlit. The deployment uses the shared engine and API rather than implementing separate retrieval or financial logic inside the UI.

The private stack is intended to include:

- FastAPI application.
- Streamlit interface.
- PostgreSQL with pgvector.
- Local filesystem storage for original documents.
- Background ingestion worker.
- Neo4j when graph functionality is enabled.
- Configurable LLM provider.

Configuration must be supplied through environment variables and a local `.env` file excluded from Git.

The application must not require users to edit source code to configure provider credentials or storage locations.

### 3.3 Local Storage Is Not the Same as Local Inference

A self-hosted deployment may store documents, chunks, embeddings, and graph data locally while sending selected retrieved passages to an external LLM API.

This is a private deployment with external inference, not a fully offline deployment.

The configured provider must be explicit. The system must document which data may leave the local environment.

A future local-inference implementation may use the same LLM adapter interface, subject to hardware, quality, and performance evaluation.

### 3.4 Shared Engine Boundary

Both deployment modes share:

- Domain models and contracts.
- Document normalization and chunking rules.
- Retrieval and ranking logic.
- Graph operations and provenance rules.
- Financial calculation and comparability logic.
- Evidence grading and bounded workflow transitions.
- Citation validation and answer synthesis.
- Core evaluation cases.

Only infrastructure-dependent behavior should vary through explicit adapters and configuration.

---

## 4. High-Level Logical Architecture

### 4.1 Document Ingestion

```text
PDF Upload
    |
    v
API Validation and Document Registration
    |
    v
Private Original-File Storage
    |
    v
Durable Ingestion Job
    |
    v
PDF Inspection and Page Classification
    |
    v
Docling Parsing
    |
    +---- Selective OCR Fallback
    |
    v
Normalized Document Tree
    |
    +---- Pages, Sections and Source Locations
    |
    +---- Structured Tables, Cells and Footnotes
    |
    v
Extraction Quality Assessment
    |
    v
Parent-Child Chunking and Stable Source IDs
    |
    +--------------------------+
    |                          |
    v                          v
PostgreSQL                 Embedding Generation
    |                          |
    |                          v
    |                      pgvector
    |
    +---- Full-Text Search
    |
    +---- Metadata and Evidence
    |
    v
Financial Fact Candidates
    |
    v
Neo4j Graph Upsert
    |
    v
Indexing and Quality Verification
    |
    v
READY or NEEDS_REVIEW
```

Fatal errors transition the ingestion job to `FAILED`. Explicit deletion transitions the document lifecycle to `DELETED`, with derived-data cleanup tracked separately where necessary.

### 4.2 Question Answering

```text
Authenticated User Question
    |
    v
Question Validation and Authorized Scope
    |
    v
Query Normalization and Variants
    |
    v
Authorization-Filtered Hybrid Retrieval
    |
    +---- Dense Search: pgvector
    |
    +---- Sparse Search: PostgreSQL Full-Text Search
    |
    v
Reciprocal Rank Fusion (RRF)
    |
    v
Cross-Encoder Reranking
    |
    v
Context Assembly
    |
    v
Graph Traversal and Evidence Validation
    |
    v
Structured Evidence Grading
    |
    +-------------------------------+
    |               |               |
    v               v               v
   PASS            RETRY          ABSTAIN
    |               |               |
    v               v               v
Deterministic    One Targeted     Insufficient
Calculations     Retrieval Retry  Evidence Response
    |               |
    |               v
    |          Grade Again
    |               |
    |          PASS or ABSTAIN
    |
    v
Grounded Answer Synthesis
    |
    v
Citation and Response Validation
    |
    v
Final Answer
    |
    v
Citations, Calculations, Limitations,
Status and Retrieval Trace ID
```

The automatic targeted retry is limited to **one retry per question workflow** in the initial implementation.

---

## 5. Component Responsibilities

| Component | Technology | Responsibility |
|---|---|---|
| API | FastAPI | Request validation, typed contracts, dependency injection and HTTP handling. |
| Private UI | Streamlit | Local upload, document status, question answering and citation display. |
| Hosted UI | To be selected | Web experience for hosted users and organizations. |
| Document parser | Docling | Primary structured PDF and table parsing. |
| OCR | Local OCR engine, such as Tesseract | Selective extraction from scanned or unreliable pages. |
| Relational database | PostgreSQL | Application records, metadata, jobs, chunks, evidence and conversations. |
| Dense retrieval | pgvector | Embedding storage and semantic similarity search. |
| Sparse retrieval | PostgreSQL full-text search | Keyword-oriented search for financial terms, periods, sections and footnotes. |
| Graph database | Neo4j | Traceable relationships among companies, filings, metrics, periods and evidence. |
| Workflow orchestration | LangGraph or an equivalent explicit state machine | Typed workflow state, conditional transitions and bounded retry behavior. |
| Reranking | Open-source cross-encoder | Rerank a bounded set of retrieved candidates. |
| LLM integration | Provider-independent adapter | Query variation, evidence grading and answer synthesis. |
| Background processing | Worker and durable job model | Asynchronous parsing, OCR, chunking, embedding and graph indexing. |
| Original-file storage | Local filesystem and S3-compatible adapter | Private, durable storage of original documents. |
| Packaging | Docker Compose | Reproducible private deployment and service wiring. |
| Testing | pytest | Unit, integration, API, retrieval, financial and security tests. |

Technology names describe the intended design. Specific models, providers, and worker or queue implementations must be selected and evaluated in their designated phases.

---

## 6. Data Architecture

### 6.2. Database Architecture

FinAudit_AI uses PostgreSQL as its primary relational database and Weaviate as its vector database. Each database serves a different purpose.

**PostgreSQL — Primary Relational Database**

PostgreSQL stores structured application data and extracted financial information. The initial schema consists of five tables:

1. `users` — Stores user account information.
2. `workspaces` — Manages temporary user workspaces and their expiration.
3. `documents` — Stores uploaded document metadata and storage references.
4. `ingestion_jobs` — Tracks document extraction jobs, their status, and errors.
5. `extracted_content` — Stores extracted document content in JSONB format, including relevant text, tables, and structured financial data.

**Weaviate — Vector Database**

Weaviate stores vector embeddings and their corresponding text chunks generated from extracted documents. It enables semantic search, allowing the system to retrieve relevant document passages based on the meaning of a user's question rather than relying only on exact keyword matches.

**Temporary File Storage**

Original uploaded files, including PDFs, spreadsheets, and images, are stored separately from both databases. PostgreSQL maintains their metadata and storage references.

**Data Processing and Retrieval Flow**

1. Users upload documents to a temporary workspace.
2. The original files are stored in temporary file storage, and their metadata is recorded in PostgreSQL.
3. Background ingestion jobs extract text, tables, and relevant financial data from the uploaded documents.
4. Extracted content is stored in PostgreSQL, while searchable text chunks and their vector embeddings are stored in Weaviate.
5. When a user asks a question, Weaviate retrieves relevant document passages. PostgreSQL provides structured financial data when needed for accurate filtering, aggregation, and calculations.
6. The retrieved information is passed to the AI component to generate an answer grounded in the uploaded documents.

**Data Lifecycle and Cleanup**

When a workspace expires, the system deletes its associated PostgreSQL records, original uploaded files, and Weaviate vectors. This ensures that temporary financial documents and their derived data do not remain stored beyond the workspace's permitted lifetime.

The initial implementation will prioritize PostgreSQL and document extraction, followed by Weaviate integration for semantic search. Additional database tables or infrastructure components will be introduced only when justified by concrete requirements.
### 6.1 PostgreSQL as the Primary Application Store

PostgreSQL stores application records, workspace metadata, document metadata, extracted content, and ingestion job status.

The initial database schema consists of **five tables**.

#### 1. `users`

Stores user account information.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `email` | VARCHAR | Unique, not null |
| `password_hash` | VARCHAR | Not null |
| `created_at` | TIMESTAMPTZ | Not null |

#### 2. `workspaces`

Represents a temporary analysis session.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `user_id` | UUID | Foreign key to `users.id`, nullable |
| `status` | VARCHAR | Not null |
| `created_at` | TIMESTAMPTZ | Not null |
| `expires_at` | TIMESTAMPTZ | Not null |

#### 3. `documents`

Stores metadata and the storage reference for each uploaded file. Original file bytes remain in temporary file/object storage, not in PostgreSQL.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `workspace_id` | UUID | Foreign key to `workspaces.id` |
| `filename` | VARCHAR | Not null |
| `file_type` | VARCHAR | Not null |
| `storage_key` | TEXT | Not null |
| `file_size` | BIGINT | Not null |
| `checksum` | VARCHAR | Not null |
| `status` | VARCHAR | Not null |
| `created_at` | TIMESTAMPTZ | Not null |

A unique constraint on `(workspace_id, checksum)` prevents duplicate registration of the same file within a workspace.

#### 4. `ingestion_jobs`

Tracks asynchronous document extraction and processing.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `document_id` | UUID | Foreign key to `documents.id` |
| `status` | VARCHAR | Not null |
| `attempt_count` | INTEGER | Not null |
| `error_code` | VARCHAR | Nullable |
| `created_at` | TIMESTAMPTZ | Not null |
| `started_at` | TIMESTAMPTZ | Nullable |
| `completed_at` | TIMESTAMPTZ | Nullable |

A document may have multiple jobs when processing requires retries.

#### 5. `extracted_content`

Stores the extracted document content in a flexible JSONB structure.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | Primary key |
| `document_id` | UUID | Unique foreign key to `documents.id` |
| `content` | JSONB | Not null |
| `created_at` | TIMESTAMPTZ | Not null |
| `updated_at` | TIMESTAMPTZ | Not null |

The JSONB content can represent extracted text, pages, sections, tables, rows, cells, and source locations. The structure varies according to the document format; separate PostgreSQL tables are not required for every document structure.

### Relationships

- One user can own multiple workspaces.
- One workspace can contain multiple documents.
- One document can have multiple ingestion jobs.
- One document has one current extracted-content record.

### Temporary Data and Cleanup

Original files, extracted content, and ingestion records are temporary and belong to the workspace lifecycle. Workspace cleanup must remove associated database records and original files from temporary storage.

Foreign keys, indexes, uniqueness constraints, and cascading deletion behavior must be implemented through Alembic migrations and verified with tests.

This is the initial physical database schema. Additional tables will be introduced only when a demonstrated requirement justifies them.|

These are logical entities, not instructions to create every table immediately. Physical schemas must be introduced through migrations during the appropriate implementation phase.

The initial implementation should use the smallest schema that supports the actual workflow. Related entities may share tables or be represented through structured fields when doing so preserves data integrity and traceability.

Organizational entities such as `Organization` and `Membership` should be introduced when organizational accounts, multiple users per organization, or hosted multi-tenant administration are required. They are not mandatory solely because the system supports temporary workspaces.

Every temporary record must belong to a workspace, directly or through a clearly defined ownership relationship. Database queries, file access, and background jobs must enforce workspace isolation.

PostgreSQL is the primary application database, but it is not the default permanent repository for original uploaded files.

### 6.2 Document Storage Boundary

Original document bytes are stored through a file-storage adapter rather than directly in a PostgreSQL column by default.

The storage adapter must support:

- Uploading a file.
- Reading or streaming a file.
- Deleting a file.
- Inspecting file metadata.
- Verifying stored content against its checksum.

The corresponding PostgreSQL document record stores an opaque `object_key` and the metadata required to identify, process, and manage the document.

An object key is an identifier, not authorization to access a file. All file access must be private and authorized.

**Initial implementation:**

- Private local filesystem storage is sufficient for development and the first private deployment.
- PostgreSQL stores the document's metadata and storage reference.
- Original files remain unchanged during processing.
- The system verifies file integrity using a cryptographic checksum, such as SHA-256.

**Hosted implementation:**

- An S3-compatible object-storage adapter may be introduced when required.
- The application depends on the storage interface rather than a specific provider.
- Storage limits and retention behavior must be explicitly configured.

The architecture must not assume that a free storage provider offers unlimited capacity or permanent availability.

The private self-hosted edition must allow customers to keep original files on infrastructure they control. The hosted edition stores files in private storage operated by or for the service.

The same application-level storage contract must be used by both deployments.

### 6.3 Parent-Child Chunking

Parent chunks preserve larger logical context. Child chunks provide smaller retrieval units, such as paragraphs, table row groups, or footnotes.

This hierarchy supports retrieval that combines precise matching with sufficient surrounding context.

Each child chunk must retain the references necessary to establish its origin and meaning, including:

- Its parent chunk.
- Its source document.
- Page and section, where available.
- Table, row, column, and footnote references, where applicable.
- Parser and extraction version.
- Relevant units, reporting periods, and quality metadata.

A chunk must not lose information required to interpret a financial value correctly.

For example, a numeric value must not be separated from the applicable row label, column header, currency, scale, or reporting period when those details are necessary to interpret it.

A table must not be divided into arbitrary fragments that separate numeric values from their headers, labels, units, or reporting periods. Table-aware extraction and chunking must preserve those relationships.

Chunking rules should be deterministic where practical. Stable identifiers and idempotent indexing must prevent duplicate records when processing is retried.

Changes to parser or chunking logic must be versioned. When a change alters the extracted structure or retrieval units, the affected derived data must be deliberately regenerated or reindexed.

Chunks, indexes, and embeddings are derived data, not replacements for the original document. They belong to the workspace lifecycle and must be deleted when that workspace is cleaned up.

A separate vector database is not required for the initial implementation. PostgreSQL-backed metadata and ordinary text retrieval may be sufficient initially. Semantic retrieval can be introduced through PostgreSQL with `pgvector` or another adapter if testing demonstrates that it is needed.

### 6.4 Financial Fact Provenance

A financial fact must carry sufficient context to identify what the number means, where it came from, and whether it was reported or derived.

Where available, this includes:

- Company and legal entity.
- Business segment.
- Metric definition.
- Value, currency, unit, scale, and sign convention.
- Fiscal period and whether the metric represents a duration or a point in time.
- Accounting basis, including GAAP, non-GAAP, or adjusted.
- Restatement status.
- Whether the value was reported, extracted, normalized, or derived.
- Source document and relevant page, section, table, row, column, or footnote.
- Extraction method and quality status.
- Relevant calculation inputs, formula, and calculation-rule version for derived values.

Not every source document will contain every attribute. Unknown information must remain unknown rather than being silently inferred and recorded as fact.

OCR-derived or uncertain figures must not automatically be treated as verified values. Extraction quality should be represented explicitly so downstream processing can distinguish reliable values from ambiguous ones.

A derived financial fact must retain references to its input facts and the calculation that produced it. Where applicable, the calculation must also retain its currency, units, rounding policy, and reporting-period assumptions.

**Evidence provenance is a core architectural invariant.** Every factual audit finding must be traceable to supporting source evidence or to a documented calculation whose inputs are traceable to source evidence.

AI-generated summaries must not become the sole source of truth for financial claims. The system must preserve the distinction between source-reported values, extracted values, calculated values, and interpretive conclusions.

Financial facts and their provenance are temporary workspace data by default. They must be removed during workspace cleanup along with the underlying derived artifacts.

### 6.5 Workspace Lifecycle and Isolation

Each analysis workspace has a defined lifecycle.

The standard lifecycle is:

`ACTIVE → EXPIRING → CLEANING → DELETED`

The implementation may introduce additional states for failed cleanup or other recovery conditions.

- `ACTIVE`: The user may upload supported files and perform authorized analysis operations.
- `EXPIRING`: The workspace has reached its configured expiration condition. New operations may be restricted while the system prepares for cleanup.
- `CLEANING`: The system removes original files, extracted data, search indexes, embeddings, cached content, temporary reports, and associated workspace records.
- `DELETED`: Cleanup has completed according to the system's defined deletion guarantees.

Workspace expiration must be based on an explicit session policy. The policy must define the inactivity period, maximum workspace lifetime where applicable, and behavior when an active analysis is still running.

Logging out should trigger workspace cleanup when the product's session policy requires it. Automatic expiration must also handle browser closures, crashes, lost connections, and abandoned workspaces.

The system must not rely exclusively on a browser event to delete sensitive data.

Workspace isolation must be enforced at the application and storage boundaries:

- Users must not be able to retrieve another workspace's documents or results.
- API requests must validate workspace ownership and authorization.
- Background jobs must carry an explicit workspace identifier and verify that the workspace is still valid before accessing its data.
- Expired or deleted workspaces must not accept new processing work.
- Cached results and retrieval indexes must not leak data between workspaces.

Cleanup must be idempotent: repeating a cleanup operation must be safe.

If cleanup fails, the system must record a safe operational error and retry according to a bounded retry policy. It must not claim that deletion is complete merely because a cleanup request was accepted.

### 6.6 Data Retention and Deletion

The default MVP retention policy is:

| Data | Default treatment |
| :--- | :--- |
| Original uploaded documents | Temporary; delete during workspace cleanup. |
| Extracted text, pages, tables, and sections | Temporary; delete during workspace cleanup. |
| Parent and child chunks | Temporary; delete during workspace cleanup. |
| Search indexes and embeddings | Temporary; delete during workspace cleanup. |
| Financial facts and intermediate calculations | Temporary; delete during workspace cleanup. |
| Conversations and generated answers | Temporary; delete during workspace cleanup. |
| Audit findings and generated reports | Temporary; delete during workspace cleanup. |
| Ingestion and analysis job records | Temporary; remove or sanitize during workspace cleanup once safe job termination and cleanup requirements are satisfied. |
| User account information | Retain only as necessary to provide the account and related services. |
| Security and operational logs | Retain only necessary, minimized metadata under a separately defined retention policy. |

The application must not place original document contents, extracted financial values, or full sensitive prompts in permanent logs merely for debugging.

Temporary data may exist in several locations during processing, including local temporary directories, caches, database rows, background-job payloads, and external AI services. The cleanup design must identify and account for each location that may contain sensitive information.

The interface must explain the workspace expiration policy before users upload sensitive documents.

If a future feature allows users to export reports, the export process must clearly explain that downloaded files are outside the platform's subsequent deletion controls. Exporting a report must not silently enable permanent retention of the original workspace.

Backup and third-party provider behavior must be documented. The system must not promise immediate deletion from every backup or external service unless that guarantee is technically supported.

The MVP must not claim that logout instantly removes every copy from every system unless the implementation has verified that behavior.

### 6.7 Hosted and Private Deployment Compatibility

The hosted and private editions share the same application logic, document-processing pipeline, data contracts, financial calculations, compliance rules, and evidence-grounding requirements.

Their infrastructure adapters may differ.

**Hosted edition:**

- PostgreSQL is operated by or for the service.
- Original documents are stored in private, configured file storage.
- Workspace quotas, resource limits, and cleanup policies protect service capacity.
- Tenant isolation is required if multiple customers share the deployment.

**Private self-hosted edition:**

- PostgreSQL runs in the customer's controlled environment.
- Original documents are stored in customer-controlled local or object storage.
- The customer controls the relevant infrastructure and resource capacity.
- The same workspace isolation and cleanup contracts apply.

The private edition must not depend on the hosted edition's storage service for ordinary document processing unless an explicitly configured external dependency is required.

If an external AI provider is used, relevant data may leave the customer's infrastructure. A fully private deployment therefore requires an appropriate local or customer-controlled inference option and must avoid unapproved external processing.

Infrastructure differences must not silently change financial calculations, compliance rules, evidence-grounding behavior, or the meaning of audit results.

### 6.8 Implementation Boundary

The initial implementation should prioritize a working, verifiable document-analysis workflow rather than introducing unnecessary infrastructure.

The initial storage architecture consists of:

1. PostgreSQL for application records and workspace metadata.
2. Private local file storage for original uploaded documents.
3. A document-processing pipeline that creates temporary extracted data and evidence references.
4. Workspace-scoped access controls.
5. Reliable workspace expiration and cleanup.
6. Tests verifying document integrity, evidence provenance, isolation, and cleanup behavior.

Additional capabilities—such as hosted object storage, vector search, distributed workers, organizational administration, and permanent audit-history storage—must be introduced only when the corresponding requirement justifies them.

All persistent and temporary data structures must be introduced through migrations and maintained through tests.

This document defines the intended architecture; it does not assert that every listed component has already been implemented. Actual implementation status must be verified against the code, configuration, and tests.

Changes to these architectural decisions must be reflected in this document and the relevant tests so implementation remains consistent with the agreed design.

## 7. Financial Knowledge Graph

### 7.1 Purpose

Neo4j represents explicit relationships between financial entities and evidence. It complements retrieval; it does not replace the original documents or become an untraceable source of truth.

### 7.2 Initial Graph Schema

```cypher
(:Company)-[:FILED]->(:Filing)
(:Filing)-[:COVERS_PERIOD]->(:FiscalPeriod)
(:Filing)-[:HAS_SECTION]->(:Section)
(:Section)-[:CONTAINS_EVIDENCE]->(:Evidence)
(:Evidence)-[:SUPPORTS]->(:FinancialFact)
(:FinancialFact)-[:ABOUT_METRIC]->(:Metric)
(:FinancialFact)-[:FOR_PERIOD]->(:FiscalPeriod)
(:FinancialFact)-[:QUALIFIED_BY]->(:Footnote)
(:FinancialFact)-[:REPORTED_BY]->(:Company)
(:FinancialFact)-[:POSSIBLY_CONFLICTS_WITH]->(:FinancialFact)
```

This is the initial logical schema. Uniqueness constraints, relationship properties and physical graph models will be finalized during the graph implementation phase.

### 7.3 Graph Integrity Rules

- Material facts must have provenance linking them to source evidence.
- Graph writes must be idempotent.
- Queries must use parameterized, allow-listed traversal patterns.
- The LLM must not generate arbitrary Cypher and execute it directly.
- Candidate relationships must be distinguished from verified relationships.
- Potential conflicts must retain provenance and review status.
- Deleting or invalidating a source document must remove or invalidate its derived graph records.
- Graph traversal must respect the authenticated user's authorized document scope.

### 7.4 Conflict Detection

Different values are not necessarily contradictory.

Before identifying a conflict, compare the metric definition, company, segment, reporting period, unit, currency, accounting basis, consolidation scope, restatement status and publication date.

If comparability cannot be established, report a potential discrepancy and explain what remains unresolved. Never silently select, average or reconcile conflicting values without a documented rule.

---

# 8. Document Ingestion and Quality Control

## 8.1 Supported Input Formats

FinAudit_AI accepts supported financial documents through a common ingestion interface. Different file formats may require different parsing strategies, but they must ultimately produce a common internal representation with source provenance and quality metadata.

The initial target formats are:

| Format | Extension / Type | Processing approach |
|---|---|---|
| PDF with embedded text | `.pdf` | Structured document parsing, with OCR where necessary. |
| Scanned PDF | `.pdf` | Page rendering and OCR, followed by structured extraction. |
| Mixed PDF | `.pdf` | Combine embedded-text extraction and selective OCR for image-based or unreliable pages. |
| Microsoft Word | `.docx` | Document parsing that preserves paragraphs, headings, tables, and relevant document structure. |
| Microsoft Excel | `.xlsx` | Workbook-aware extraction preserving worksheets, cell coordinates, formulas where available, displayed values, headers, and relevant number formats. |
| CSV | `.csv` | Delimited-text parsing with explicit encoding, delimiter, and column validation. |
| Standalone images | `.png`, `.jpg`, `.jpeg`, `.tiff` | Image validation, OCR, and layout-aware extraction where supported. |

These are the intended target formats. Each format must be marked as supported only after its parser, validation rules, and tests are implemented.

Legacy `.doc` and `.xls` files, password-protected documents, archives, and other formats are not automatically supported. They require explicit handling and must be rejected with a clear error or processed through a separately approved conversion path.

The ingestion interface must not assume that every document contains selectable text. Scanned documents, photographed receipts, image-based tables, and mixed-content PDFs require different extraction strategies.

## 8.2 Ingestion State Machine

The ingestion pipeline follows a controlled state machine.

```text
RECEIVED
   |
   v
VALIDATING
   |
   v
QUEUED
   |
   v
PARSING
   |
   v
NORMALIZING
   |
   v
CHUNKING
   |
   v
EMBEDDING  (when semantic retrieval is enabled)
   |
   v
INDEXING
   |
   v
READY
```

`EMBEDDING` may be skipped when embeddings are not required. `INDEXING` must still establish whatever retrieval structures the configured implementation requires.

The following states may be entered when applicable:

- `NEEDS_REVIEW`: processing produced usable content but quality problems require caution or review.
- `FAILED`: a fatal processing error prevents the document from being used as intended.
- `REJECTED`: validation failed before processing was accepted.
- `DELETING`: cleanup has started.
- `DELETED`: deletion has completed according to the defined cleanup guarantees.

Graph construction is not a mandatory ingestion stage. If a future implementation introduces a knowledge graph, it may add a separately versioned stage. The initial pipeline must not depend on graph construction unless the implemented product requires it.

Deletion is a separate lifecycle concern. A deletion request may interrupt ingestion at any stage, and the system must prevent subsequent stages or retries from recreating deleted workspace data.

Deletion completion must be tracked separately when asynchronous cleanup remains pending.

Partial page-level quality problems must be recorded without unnecessarily discarding otherwise usable content. However, the system must not mark a document fully `READY` if unresolved problems make the intended analysis unreliable.

Every transition must be validated. Invalid transitions must be rejected rather than silently accepted.

Processing must be idempotent where practical. Retrying a job must not create duplicate chunks, financial facts, embeddings, or index entries.

## 8.3 File Validation and Type Detection

Before parsing begins, the system must validate each uploaded file.

Validation includes:

- Configured maximum file size.
- Allowed extensions.
- MIME type and file-signature checks.
- Format-specific limits, such as PDF page count, workbook size, image dimensions, and document complexity.
- File readability and basic structural validity.
- Workspace storage quota and resource limits.
- Password protection or encryption that prevents supported processing.

File extensions and client-supplied MIME types are not sufficient evidence of the actual file format. The implementation must inspect file signatures and use a format-appropriate validation library.

Unsupported, malformed, encrypted, or over-limit files must be rejected with a safe, actionable error message.

The system must not silently convert a rejected file into a different format or claim that processing succeeded.

Files must be assigned opaque internal identifiers and storage keys. Original filenames are retained only as display metadata and must be sanitized before being displayed or used in logs.

## 8.4 Parsing Policy

Docling is the primary candidate for structured parsing of supported document types, subject to compatibility testing and the project's installed dependencies. It must not be assumed to handle every file format or extraction scenario perfectly.

Format-specific parsers or OCR adapters may be used when they provide better or necessary coverage.

The parsing layer must produce a common internal representation that preserves, where available:

- Document identity and format.
- Page identity and reading order.
- Section hierarchy and headings.
- Paragraphs and text blocks.
- Table captions, headers, rows, and cells.
- Spreadsheet worksheet names and cell coordinates.
- Units, currencies, and reporting periods.
- Footnote markers and relationships.
- Image and chart locations.
- Source locations needed for evidence citations.
- Parser version, extraction method, and quality diagnostics.

The original uploaded file must remain unchanged during processing. Extracted representations are derived data and must retain a reference to the original document.

### 8.4.1 PDF Documents

For PDFs with reliable embedded text, the parser should extract text and layout directly.

For scanned PDFs, pages must be rendered into images and processed through OCR or an appropriate document-understanding pipeline.

Mixed PDFs may contain both selectable text and scanned pages. The pipeline must assess extraction quality at page level and apply OCR selectively when needed.

The implementation must avoid blindly combining embedded text and OCR output from the same content, which can introduce duplicated paragraphs and incorrect values.

PDF page numbers used in citations must be defined consistently. Where PDF page indices differ from printed page labels, both may be preserved when available.

### 8.4.2 Word Documents

For `.docx` files, extraction should preserve paragraph order, headings, tables, and relevant structural relationships.

Headers, footers, footnotes, and comments must be handled according to explicit implementation requirements. Their presence must not be assumed to mean they have been extracted successfully.

Source references should identify the document and the closest reliable location available, such as a section heading, paragraph, or table.

### 8.4.3 Excel and CSV Files

Spreadsheet ingestion must preserve the structure necessary to interpret financial data correctly.

For Excel workbooks, relevant metadata includes:

- Workbook and worksheet identity.
- Cell coordinates.
- Row and column headers.
- Formulas and stored or calculated values, where available.
- Number formats, currency indicators, and percentage formats.
- Merged cells and relevant table boundaries.
- Hidden worksheets or rows where applicable to the configured audit policy.

A formula stored in a workbook is not necessarily equivalent to a freshly recalculated result. The system must distinguish the formula from the available stored value and must not claim that formulas were recalculated unless it actually performed that operation.

CSV ingestion must handle encoding, delimiters, quoting, headers, and malformed rows explicitly.

Spreadsheet values must not be flattened into plain text in a way that loses their relationship to their headers, reporting periods, or units.

### 8.4.4 Standalone Images

Standalone images, including photographs and scanned receipts, require image validation followed by OCR or an appropriate document-understanding pipeline.

The system should preserve:

- Image identity.
- Extracted text and reading order, where available.
- Bounding boxes or equivalent location metadata, where supported.
- Table and field relationships, where detected.
- OCR confidence or equivalent quality diagnostics, where available.

Image rotation, low resolution, blur, skew, and poor lighting can reduce extraction quality. The pipeline must record relevant quality problems and request a clearer source or manual review when necessary.

An image must not be treated as reliably understood merely because OCR returned some text.

### 8.4.5 Tables, Charts, and Financial Layouts

Financial tables require special handling because the meaning of a value depends on its labels, headers, units, and reporting periods.

The parser must preserve table relationships where possible and flag malformed or ambiguous tables for review.

Charts must not be assumed to be equivalent to structured tables. Values inferred visually from chart bars, lines, or axes must not be treated as exact financial facts unless an explicitly validated extraction method supports that level of precision.

Ambiguous chart values, missing headers, conflicting units, and unresolved footnote references must be flagged rather than guessed.

## 8.5 Normalization and Common Representation

After extraction, supported content is transformed into a common internal representation.

Normalization may include:

- Consistent date representation.
- Explicit currencies, units, and scale.
- Preservation of original numeric text alongside normalized values when useful.
- Standardized document and source-location identifiers.
- Explicit missing-value and extraction-quality states.
- Normalized table structures.
- Links between extracted financial facts and their source evidence.

Normalization must not silently change the meaning of the source.

For example, a value shown in thousands must not be interpreted as a value in single currency units without recording the applicable scale.

Unknown currencies, ambiguous dates, uncertain signs, and conflicting reporting periods must remain explicitly uncertain until resolved.

Original extracted text must remain available within the workspace when needed to verify normalization decisions.

## 8.6 Quality Signals and Review Policy

The system must record quality diagnostics appropriate to each file format.

Common signals include:

- File open and parse success.
- Total and successfully processed page counts.
- Text coverage and empty-page ratio.
- OCR confidence, where available.
- Disagreement between OCR and embedded text, where measurable.
- Table integrity and missing headers.
- Spreadsheet formula/value availability.
- Unresolved values or footnote references.
- Availability of page and source-location metadata.
- Parser warnings and extraction failures.

Format-specific signals must be used where generic PDF-oriented measures are not meaningful. For example, an Excel workbook should be evaluated using worksheet, cell, formula, and table diagnostics rather than a PDF page-coverage metric.

Quality thresholds must be established using representative test fixtures. A successful parser call alone is not sufficient to mark a document `READY`.

The system must distinguish:

- Successfully extracted and sufficiently reliable content.
- Partially extracted content that remains useful with explicit limitations.
- Content that requires review before a particular audit operation.
- Content that cannot be processed safely or reliably.

A quality problem affecting one page must not automatically invalidate an entire document when the remaining content can be processed safely.

Conversely, a document must not be considered fully reliable when missing pages, uncertain values, or malformed tables could materially affect the audit result.

Quality metadata must be available to downstream retrieval and compliance logic so low-confidence extracted values can be excluded, qualified, or routed for review as appropriate.

## 8.7 File Safety and Resource Isolation

Uploaded files and extracted content must be treated as untrusted input.

The ingestion implementation must:

- Validate file size, extension, MIME type, and file signature.
- Enforce configured page, image, workbook, and processing limits.
- Apply parsing time and memory limits.
- Avoid executing embedded scripts, macros, links, or attachments.
- Use opaque storage keys and sanitized display filenames.
- Prevent uploaded content from changing system instructions or invoking unauthorized tools.
- Isolate parsers in workers or containers with limited permissions where practical.
- Prevent one workspace from consuming excessive resources or accessing another workspace's data.
- Keep sensitive document contents out of ordinary application logs.
- Ensure cleanup covers original files, extracted content, derived records, indexes, embeddings, caches, and temporary artifacts.

PDFs, office documents, and images may contain malicious or malformed content. Parsing libraries must be kept updated, and file processing must not run with unnecessary filesystem, network, or operating-system privileges.

If malware scanning is introduced, it must be an explicit part of the validation pipeline. The system must not claim that files are malware-scanned unless an actual scanning component is configured and operating.

## 8.8 Workspace Cleanup and Ingestion Cancellation

Document ingestion is part of the temporary workspace lifecycle defined in Section 6.

When a workspace expires or is explicitly ended:

1. Prevent new ingestion and analysis work from being scheduled for that workspace.
2. Cancel or safely terminate active processing where practical.
3. Prevent retries from recreating workspace data.
4. Delete original uploaded files.
5. Delete extracted text, tables, chunks, embeddings, indexes, and temporary results.
6. Remove associated temporary database records and caches.
7. Verify cleanup according to the defined deletion guarantees.
8. Record only the minimum operational metadata needed to track cleanup failures and retries.

Cleanup must be idempotent and must tolerate partially completed ingestion jobs.

If a background job finishes after its workspace has expired, it must not publish results or recreate deleted records.

The system must distinguish between a deletion request, a cleanup operation in progress, and confirmed cleanup completion.

## 8.9 Testing Requirements

The ingestion pipeline must be tested against representative files from every format claimed to be supported.

The initial test suite should include:

- Text-based PDFs.
- Scanned PDFs.
- PDFs containing both embedded text and scanned pages.
- Word documents containing paragraphs and tables.
- Excel workbooks containing headers, formulas, numeric values, and multiple worksheets.
- CSV files with supported encodings and delimiters.
- Clear and low-quality images.
- Documents with rotated pages, missing text, malformed tables, or ambiguous values.
- Empty, corrupt, encrypted, oversized, and unsupported files.
- Repeated processing attempts and interrupted jobs.
- Workspace expiration during ingestion.
- Cross-workspace access attempts.
- Cleanup failures and retry behavior.

Expected extraction results must be checked against known fixtures. Tests should verify not only that parsing completes, but also that important financial values, units, table relationships, and source locations are preserved.

External AI providers should not be required for deterministic ingestion tests unless a specific integration test is explicitly designed to exercise them.

A format must not be advertised as supported until its validation, extraction behavior, quality handling, and cleanup behavior have passed the applicable tests.

## 9. Retrieval and Ranking

### 9.1 Query Processing

Preserve the user's original question unchanged. Generate up to three query variants that may target alternate terminology, metric names, fiscal periods or footnote language.

Query expansion must not change the requested scope or bypass authorization.

### 9.2 Hybrid Retrieval

**Dense retrieval:** Embed the question and search child-chunk embeddings using pgvector.

**Sparse retrieval:** Search normalized content and relevant metadata using PostgreSQL full-text search or a separately justified BM25 implementation.

Both retrieval paths must apply authorized organization and document filters before returning candidates.

Each retrieval result retains its source ID, rank, score and retrieval method.

### 9.3 Reciprocal Rank Fusion

Combine dense and sparse rankings using Reciprocal Rank Fusion:

\[
\operatorname{RRF}(d)=
\sum_{r\in R}\frac{1}{k+\operatorname{rank}_r(d)}
\]

Here, \(d\) is a candidate document or chunk, \(R\) is the set of ranked retrieval lists, and \(k\) is a damping constant.

Choose and document the value of \(k\), evaluate ranking quality, and deduplicate by stable chunk ID before reranking.

PostgreSQL full-text search must not be described as BM25 unless the selected implementation actually uses BM25.

### 9.4 Cross-Encoder Reranking

A cross-encoder evaluates query-candidate pairs jointly and reranks a bounded candidate set.

The chosen model must be evaluated for relevance, license, download size, CPU/RAM use and latency. Retain retrieval and reranker scores for evaluation and debugging, without treating them as calibrated probabilities of factual correctness.

A controlled fallback may disable reranking when unavailable, but the system must not claim equivalent quality without evidence.

### 9.5 Context Assembly

The context builder must:

- Select relevant child chunks.
- Expand to parent sections when context is needed.
- Retrieve linked tables and footnotes.
- Deduplicate overlapping chunks and repeated headers.
- Preserve source metadata.
- Enforce strict prompt and token budgets.
- Prioritize direct evidence and relevant qualifications.

### 9.6 Retrieval Evaluation

Maintain a manually labelled evaluation set containing questions, expected relevant source IDs and whether an answer is possible.

Measure Recall@k, MRR or nDCG where appropriate, latency, reranker impact and unsupported-answer frequency.

A semantically similar passage from the wrong fiscal period is an incorrect retrieval result.

---

## 10. Agentic Workflow and Evidence Grading

### 10.1 Workflow State

The logical workflow state contains:

```text
original_question
query_variants
authorized_scope
dense_hits
sparse_hits
fused_hits
reranked_hits
graph_evidence
evidence_grade
retry_count
targeted_query
calculations
answer_draft
citations
final_status
```

The implementation must use typed state and explicit, testable transitions.

### 10.2 Workflow Stages

1. Validate the question and resolve authorized scope from server-side identity.
2. Generate up to three query variants.
3. Run dense and sparse retrieval with authorization filters.
4. Merge rankings using RRF and rerank candidates.
5. Expand retrieved chunks to related sections, tables and footnotes.
6. Traverse the graph for relevant entities, metrics, periods and relationships.
7. Grade evidence for relevance, direct support, period alignment, unit alignment, provenance and conflicts.
8. If evidence passes, perform validated deterministic calculations and synthesize a grounded answer.
9. If evidence fails, conduct one targeted retry based on the identified missing evidence.
10. Grade the second result and either answer, partially answer or abstain.

### 10.3 Evidence Grade Contract

The evidence grader returns structured data containing:

- `relevant`
- `sufficient`
- `direct_support`
- `period_aligned`
- `units_aligned`
- `has_conflicting_values`
- `source_provenance_complete`
- `missing_evidence`
- `decision`
- `explanation_code`

The decision is one of `PASS`, `RETRY` or `ABSTAIN`.

Unknown alignment must be represented explicitly rather than assumed to be valid. Invalid grader output must never default to `PASS`.

### 10.4 Bounded Execution

The initial implementation allows at most one automatic targeted retry after the first retrieval pass.

Enforce:

- Maximum retry count.
- Request and provider timeouts.
- Maximum retrieval candidates.
- Maximum prompt and output tokens.
- Bounded provider retries.
- Graph traversal limits.
- Concurrency and rate limits.

The workflow must not repeat an unchanged query indefinitely or allow the LLM to control authorization.

### 10.5 Prompt-Injection Resistance

Retrieved document content is evidence data, not executable instruction.

The grading and synthesis components must not follow instructions embedded in uploaded documents that request secrets, altered authorization, arbitrary tool calls or access to unrelated data.

Only narrow tools with typed arguments and server-side authorization may be exposed to the workflow.

---

## 11. Financial Calculations and Answer Integrity

### 11.1 Calculation Layer

Financial calculations live in dedicated, tested Python modules, independently of prompts and orchestration frameworks.

The layer supports, as appropriate:

- Absolute change.
- Percentage change.
- Compatible unit normalization.
- Comparable-period checks.
- Metric and accounting-basis checks.
- Restatement handling.
- Reconciliation of conflicting values.

A common percentage-change formula is:

\[
\text{Percentage Change}=
\frac{\text{Current}-\text{Prior}}
{|\text{Prior}|}\times100
\]

This formula requires an explicit policy for zero and negative baselines. A zero baseline must not produce infinity or a misleading percentage. The system must explain when a percentage change is undefined or use an explicitly documented alternative.

### 11.2 Comparability Requirements

Before calculating, validate:

- Metric definition.
- Company and segment.
- Reporting periods and durations.
- Currency and units.
- Accounting basis.
- Restatement status.
- Sign conventions.
- Reported versus derived values.

Currency conversion must not be performed silently. It requires a documented exchange-rate source and policy.

### 11.3 Calculation Provenance

Every material derived value must include:

- Calculation name.
- Input financial fact identifiers.
- Input values and periods.
- Formula.
- Result and unit.
- Relevant source citations.
- Any limitations or comparability warnings.

The LLM explains the validated result; it does not replace the calculation engine.

---

## 12. Answer Schema and Citation Validation

### 12.1 Response Contract

The final answer uses a Pydantic-validated response model. The following illustrates the intended structure:

```json
{
  "answer": "Grounded explanation of the financial question.",
  "status": "answered",
  "claims": [
    {
      "text": "A material factual claim.",
      "citations": [
        {
          "document_id": "document-id",
          "page": 12,
          "section": "Revenue",
          "table_id": "table-id",
          "chunk_id": "chunk-id"
        }
      ]
    }
  ],
  "calculations": [],
  "limitations": [],
  "retrieval_trace_id": "trace-id"
}
```

Allowed answer statuses:

- `answered`
- `partially_answered`
- `insufficient_evidence`

The final schema must define field types, validation rules and appropriate optional fields. The example above is illustrative, not the final API contract.

### 12.2 Citation Validation

Before returning an answer, verify that:

- Each cited identifier exists.
- The evidence belongs to the current authorized corpus.
- The cited source was actually available to the answer workflow.
- Page, table and section metadata are genuine.
- Material claims are supported by the associated evidence.

Table-based claims should cite the relevant table and row/column when available. Adjusted financial conclusions should cite both the relevant values and explanatory footnotes.

If a source location cannot be reliably established, disclose the limitation instead of fabricating a citation.

A citation establishes provenance, not automatic correctness.

---

## 13. API and User Experience

### 13.1 Initial API Surface

| Endpoint | Responsibility |
|---|---|
| `GET /health` | API liveness check without exposing secrets. |
| `POST /api/v1/documents` | Validate and register a document; return document and job IDs. |
| `GET /api/v1/documents` | List authorized documents. |
| `GET /api/v1/documents/{id}` | Retrieve document status and quality summary. |
| `DELETE /api/v1/documents/{id}` | Initiate auditable document deletion. |
| `POST /api/v1/query` | Query an authorized document collection. |
| `GET /api/v1/jobs/{id}` | Retrieve ingestion job status and safe error codes. |

Endpoint implementation must follow the planned development phases. The list defines intended contracts, not currently implemented behavior.

### 13.2 API Requirements

- Use typed request and response models.
- Validate upload constraints and request sizes.
- Return safe error codes rather than stack traces.
- Include appropriate request, job and trace identifiers.
- Apply authorization to every protected operation.
- Use pagination and input bounds where relevant.
- Keep long-running ingestion outside the user-facing request lifecycle.
- Avoid leaking the existence or content of unauthorized document IDs.

### 13.3 UI Requirements

The interface must support:

- Uploading PDFs and displaying upload progress.
- Document status and extraction warnings.
- Document selection within authorized scope.
- Questions and answers with citations.
- Display of calculation formulas, results and limitations.
- Clear insufficient-evidence responses.
- Document deletion with an explanation of the deletion lifecycle.

The private Streamlit UI must call the shared engine/API. It must not duplicate the core retrieval or financial calculation logic.

---

## 14. Security, Privacy and Auditability

### 14.1 Authentication and Authorization

Hosted mode requires a maintained authentication solution and server-side organization membership enforcement.

The system must not store plaintext passwords. Sessions, cookies, email verification where applicable, and authentication rate limits must be handled securely.

Private mode still requires documented network-binding and access-control expectations. A self-hosted application must not be assumed safe merely because it runs locally.

### 14.2 Tenant Isolation

Every tenant-owned record must have an enforceable organization ownership relationship.

Tenant scope must derive from authenticated server-side context, not solely from a client-supplied organization ID.

Isolation must apply to:

- Document metadata.
- Original-file access.
- Chunks and evidence.
- Dense and sparse retrieval.
- Graph traversal.
- Conversations and messages.
- Caches and exports.
- Deletion operations.

Cross-tenant tests must demonstrate that one organization cannot access another organization's documents or derived information.

### 14.3 Secrets and Provider Boundaries

- Commit `.env.example` with placeholders only.
- Exclude `.env`, provider keys, credentials and private documents from Git.
- Keep secrets out of frontend responses and ordinary logs.
- Use deployment secret management in hosted mode.
- Restrict local secret-file permissions where supported.
- Document key rotation and revocation.
- Review provider data terms and information sent to external inference services.

The hosted provider-key model—operator-managed or securely managed per organization—remains an explicit decision until resolved.

### 14.4 Logging and Audit Events

Use structured logs with request, job and trace identifiers.

Do not log full prompts, complete retrieved chunks, raw documents or API keys by default.

Audit events should capture relevant security and lifecycle actions, such as document access, deletion requests, permission changes and important processing outcomes, using controlled metadata.

Audit records must not become a secondary store of sensitive document content.

### 14.5 Retention and Deletion

Document deletion is a workflow, not just a database operation.

The deletion lifecycle must cover:

1. Original stored files.
2. Extracted text and normalized document data.
3. Parent and child chunks.
4. Embeddings and search indexes.
5. Table and footnote records.
6. Graph nodes and relationships.
7. Cached answers and derived artifacts.
8. Applicable conversation references and temporary files.

The system must track cleanup status and define how backups expire. Any pending deletion must be represented transparently.

### 14.6 Prompt and Upload Safety

Uploaded PDFs and extracted text are untrusted inputs. Enforce file limits, parser resource limits, opaque storage paths, safe error handling and restrictions on arbitrary HTML rendering.

Do not allow untrusted document content or LLM-generated queries to bypass access controls or execute arbitrary SQL/Cypher.

---

## 15. Background Processing and Reliability

### 15.1 Worker Responsibilities

The ingestion worker handles:

- PDF inspection and parsing.
- Selective OCR.
- Normalization and quality checks.
- Chunk generation.
- Embedding generation.
- Search indexing.
- Financial fact extraction.
- Graph upserts.

These tasks must not execute synchronously inside the upload request.

### 15.2 Job Reliability

The system must persist job state and support:

- Idempotent stage execution.
- Bounded retries for transient failures.
- Safe handling of permanent failures.
- Duplicate-job detection.
- Worker restart recovery.
- Concurrency limits.
- Dead-letter or documented manual-retry handling.
- Stage-level timing and safe failure codes.

The queue technology remains open until the worker implementation phase, when deployment simplicity, durability and idempotency will guide the decision.

### 15.3 Observability

Operational monitoring should include:

- API and database health.
- Worker and graph-service health.
- Object-storage connectivity.
- Ingestion duration and parser failures.
- OCR fallback rate.
- Retrieval and reranking latency.
- LLM latency, usage and cost.
- Retry and abstention rates.
- Job backlog and failure counts.

Timeouts, resource limits, bounded retries and graceful error responses are required.

---

## 16. Repository Structure and Architectural Boundaries

The intended repository structure is:

```text
financial-audit-engine/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── routes/
│   │   ├── dependencies.py
│   │   └── error_handlers.py
│   ├── core/
│   │   ├── config.py
│   │   ├── logging.py
│   │   └── security.py
│   ├── domain/
│   │   ├── documents.py
│   │   ├── evidence.py
│   │   ├── financial_facts.py
│   │   └── answers.py
│   ├── ingestion/
│   │   ├── inspect_pdf.py
│   │   ├── parse_docling.py
│   │   ├── ocr_fallback.py
│   │   ├── normalize.py
│   │   ├── quality.py
│   │   └── chunking.py
│   ├── retrieval/
│   │   ├── dense.py
│   │   ├── sparse.py
│   │   ├── fusion.py
│   │   ├── reranking.py
│   │   └── context_builder.py
│   ├── graph/
│   │   ├── schema.py
│   │   ├── repository.py
│   │   └── traversal.py
│   ├── agent/
│   │   ├── state.py
│   │   ├── workflow.py
│   │   ├── grading.py
│   │   └── prompts/
│   ├── finance/
│   │   ├── calculations.py
│   │   ├── comparability.py
│   │   └── reconciliation.py
│   ├── llm/
│   │   ├── protocol.py
│   │   ├── mock_client.py
│   │   └── providers/
│   ├── storage/
│   │   ├── documents.py
│   │   ├── chunks.py
│   │   ├── conversations.py
│   │   └── jobs.py
│   └── workers/
│       └── ingestion_worker.py
├── ui/
│   ├── streamlit_app.py
│   └── components/
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── api/
│   ├── retrieval_eval/
│   ├── security/
│   └── fixtures/
├── scripts/
├── docs/
│   ├── architecture.md
│   ├── PROJECT_STATUS.md
│   └── decisions/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

This is a target structure, not a requirement to create all directories immediately.

### 16.1 Layer Responsibilities

- **API:** HTTP contracts, authentication dependencies and request validation.
- **Domain:** Typed business concepts and contracts independent of infrastructure.
- **Ingestion:** PDF processing, normalization, quality checks and chunking.
- **Retrieval:** Dense and sparse search, fusion, reranking and context assembly.
- **Graph:** Graph persistence and approved traversal operations.
- **Agent:** Explicit workflow state, evidence grading and bounded transitions.
- **Finance:** Pure calculations, comparability checks and reconciliation.
- **LLM:** Provider-independent contracts, mocks and provider adapters.
- **Storage:** Database and original-file persistence boundaries.
- **Workers:** Asynchronous job execution and recovery.
- **UI:** Presentation and interaction without duplicating business logic.

### 16.2 Coding Rules

- Use type hints and Pydantic for validated external contracts.
- Use database migrations rather than production schema auto-creation.
- Use parameterized SQL/Cypher and explicit authorization checks.
- Keep pure calculations separate from I/O.
- Use asynchronous code where it is beneficial and supported end-to-end.
- Keep functions focused and avoid unnecessary abstractions.
- Pin dependencies through a reproducible dependency strategy.
- Do not silently swallow unexpected exceptions.
- Inspect existing code and Git state before editing.
- Implement one bounded change at a time.
- Never claim that tests passed unless their results were actually observed.

---

## 17. Testing and Evaluation Architecture

### 17.1 Test Layers

| Test layer | Primary coverage |
|---|---|
| Unit tests | Calculations, comparability, chunking, stable IDs, RRF and schema validation. |
| Parser fixtures | Text PDFs, scans, mixed PDFs, financial tables, footnotes and malformed files. |
| Integration tests | PostgreSQL, pgvector, object storage, graph persistence and worker idempotency. |
| API tests | Request validation, response contracts, status codes, authorization and safe errors. |
| Retrieval evaluation | Dense versus sparse search, RRF, reranking and expected evidence recall. |
| Workflow tests | PASS, RETRY and ABSTAIN transitions, retry bounds and provider timeouts. |
| Financial evaluation | Known numeric answers, unit mismatch, wrong periods, accounting-basis mismatch and restatements. |
| Security tests | Tenant isolation, unauthorized IDs, prompt injection, upload abuse and secret leakage. |
| Deployment smoke tests | Clean startup, migrations, health checks, upload, query and deletion. |

### 17.2 Deterministic Testing

Most tests must run without paid API calls or network access.

Use mocked LLM responses, fixed fixtures and known expected results for unit and API tests.

A smaller, separately labelled live-provider evaluation suite may measure model quality, provider compatibility, cost and latency.

### 17.3 Required Financial Cases

At minimum, validate:

- Change from 10 to 12 gives +20%.
- Change from 20 to 18 gives -10%.
- Zero baseline is handled explicitly.
- Incompatible units are not silently compared.
- Quarterly and annual durations are not treated as equivalent.
- GAAP and adjusted figures retain their accounting-basis distinction.
- Restated prior periods are handled according to the requested basis.
- Every derived result traces to its input evidence.

### 17.4 Release Gates

Do not treat a successful HTTP status as proof of correct behavior.

Release readiness requires evidence that:

- Citations are real and authorized.
- Unsupported questions abstain appropriately.
- Financial calculations are deterministic.
- Graph facts retain provenance.
- Retrieval quality has been evaluated.
- Retry bounds cannot be bypassed.
- Tenant-isolation tests pass before hosted multi-user access is enabled.
- Deletion and restoration procedures have been tested.
- Secrets and sensitive content are not leaked through logs or responses.

---

## 18. Deployment and Configuration

### 18.1 Configuration Categories

The following names are illustrative and must be reconciled with the actual settings implementation:

```dotenv
APP_ENV=development
API_V1_PREFIX=/api/v1

DATABASE_URL=postgresql+psycopg://...

OBJECT_STORAGE_BACKEND=local

LLM_PROVIDER=mock
LLM_API_KEY=

EMBEDDING_MODEL=
RERANKER_MODEL=

GRAPH_ENABLED=false

MAX_UPLOAD_MB=
MAX_PDF_PAGES=
MAX_RETRIEVAL_CANDIDATES=
MAX_AGENT_RETRIES=1
```

Real credentials must never appear in `.env.example`, documentation, source code or Git history.

Required configuration must be validated at startup with clear, safe errors.

### 18.2 Development Profile

- Mock LLM responses.
- Local test fixtures.
- Local PostgreSQL/pgvector.
- Local original-file storage.
- Small representative PDF fixtures.
- Strict resource limits.
- Graph services enabled only when required by the current phase.

### 18.3 Staging Profile

- Public financial filings or synthetic test data.
- Managed secrets and configured usage limits.
- Private object storage.
- Tenant-isolation tests.
- Health checks, logs, metrics and backup policies.

Do not introduce confidential customer data until provider data flows and applicable controls have been reviewed.

### 18.4 Production Profile

Production deployment requires measured resource limits, reviewed provider terms, access controls, retention and deletion policies, tested backups, recovery procedures, incident response and a documented upgrade process.

Do not describe the system as fully secure, compliant or production-ready without evidence supporting those claims.

---

## 19. Architecture Decisions and Open Questions

### 19.1 Fixed Architectural Decisions

The following decisions are established by the project blueprint:

1. One shared core engine serves two deployment modes.
2. PostgreSQL is the primary relational store.
3. pgvector is the initial dense retrieval implementation.
4. PostgreSQL full-text search is the initial sparse retrieval baseline.
5. Neo4j provides graph capabilities in its dedicated implementation phase.
6. Docling is the primary PDF parser.
7. OCR is selective rather than automatically applied to every page.
8. Financial arithmetic is performed by deterministic code.
9. The agent workflow allows one targeted retry initially.
10. Insufficient evidence must result in an honest limited answer or abstention.
11. The private UI initially uses Streamlit.
12. Docker Compose provides the initial private deployment.
13. Development proceeds in testable phases, not through a one-shot code generation process.

### 19.2 Decisions Still Open

The following must not be silently treated as finalized:

- Exact LLM provider and model.
- Exact embedding model.
- Exact cross-encoder model.
- Exact background queue and worker technology.
- Exact S3-compatible storage provider.
- Hosted authentication provider.
- Hosted web frontend framework.
- Provider-key ownership model.
- Retrieval thresholds and evidence-grade thresholds.
- Representative-document quality thresholds.
- Final graph constraints and graph deployment model.

Each material decision must be recorded in the decision log with its rationale, consequences and relevant evaluation results.

---

## 20. Implementation Order

Implementation follows the project blueprint's phase sequence:

| Phases | Scope |
|---|---|
| 0–2 | Project setup, API skeleton, configuration, PostgreSQL and migrations. |
| 3–6 | Original-file storage, PDF inspection, normalization, quality checks, OCR and tables. |
| 7–10 | Parent-child chunking, embeddings, sparse retrieval, RRF and cross-encoder reranking. |
| 11–14 | Financial knowledge graph, deterministic calculations, evidence grading and grounded answer synthesis. |
| 15–16 | Document/query APIs, background workers and resilient ingestion. |
| 17–19 | Private Streamlit deployment, hosted authentication, tenant isolation and hosted infrastructure. |
| 20 | Full evaluation, security hardening, operational review and release readiness. |

These are planned phases, not claims of completed implementation. Work must resume from the actual repository state and `docs/PROJECT_STATUS.md`.

---

## 21. Session Handoff and Change Control

At the end of every coding session, update `docs/PROJECT_STATUS.md` with:

- Current phase and exact sub-step.
- Files created or changed.
- Commands run and observed outcomes.
- Tests passing, failing or not yet run.
- Known bugs and the next smallest task.
- Decisions made and their rationale.
- Deviations from this architecture and whether they are approved.

At the start of a new session:

1. Read this architecture document and `docs/PROJECT_STATUS.md`.
2. Inspect the repository and current Git diff.
3. Verify the environment and relevant configuration.
4. Confirm the next task and its acceptance criteria.
5. Make the smallest justified change.
6. Run the relevant tests and record the actual result.

If a proposed change conflicts with this document, stop and resolve the conflict explicitly before implementation.

---

## 22. Definition of Architectural Success

The intended architecture is successful when the implemented and tested system can:

- Ingest text-based, scanned and mixed PDFs while preserving source locations.
- Preserve financial table relationships, units, reporting periods and footnotes.
- Detect and surface unreliable extraction.
- Retrieve evidence using evaluated hybrid search and reranking.
- Traverse a provenance-linked financial knowledge graph.
- Validate financial comparability and perform reproducible calculations.
- Produce answers whose material factual claims have validated citations.
- Retry retrieval once in a controlled manner and abstain when evidence remains insufficient.
- Process documents asynchronously and recover safely from worker failures.
- Enforce tenant isolation throughout every relevant data path before hosted multi-user rollout.
- Delete original files and associated derived data according to a documented lifecycle.
- Operate through both deployment modes using the same core engine.
- Pass the defined financial, retrieval, API, security and deployment tests.

**The governing rule is simple:** architecture decisions define what we intend to build; implementation evidence and tests determine what we can truthfully claim has been built.

End of architecture specification.
