# ADR-001: Temporary Document Storage

- **Status:** Accepted
- **Date:** 2026-10-21

## Context

FinAudit_AI allows users to upload financial documents and analyze their contents. These documents may contain sensitive financial information and can consume significant storage.

The system should not retain uploaded financial data indefinitely by default. Users should be able to work with their documents during a temporary workspace session without requiring permanent storage.

## Decision

1. Original uploaded files will be stored outside PostgreSQL through a document storage adapter.
2. The initial implementation will use private local filesystem storage.
3. PostgreSQL will store document metadata and temporary derived data, including extracted text, chunks, financial facts, and audit findings.
4. Workspace data will be deleted when the user logs out or the workspace expires.
5. Automatic expiration and cleanup will handle abandoned sessions, including browser closures and unexpected disconnections.
6. Cleanup must be idempotent, and the system must not report successful deletion until deletion has been verified to the extent supported by the storage system.
7. Payment and subscription functionality are outside the current MVP scope.

## Rationale

- Minimize unnecessary retention of sensitive financial information.
- Avoid storing large original files directly in PostgreSQL.
- Keep the initial implementation simple and manageable.
- Preserve the ability to introduce alternative storage adapters for hosted and private deployments later.

## Consequences

### Positive

- Reduces long-term storage requirements.
- Supports a privacy-focused temporary workspace model.
- Keeps original files separate from structured application data.
- Allows future storage implementations without redesigning the entire application.

### Trade-offs and responsibilities

- Workspace expiration and cleanup must be implemented and tested.
- Cleanup must cover original files, extracted content, chunks, financial facts, findings, indexes, caches, and associated temporary records.
- Background jobs must not recreate data after a workspace has expired or been deleted.
- Users should be informed that documents and analysis results are temporary.
- Backups, logs, and external AI providers require separate retention policies where applicable.
- Private deployments must use customer-controlled storage and appropriately configured AI processing to preserve their intended privacy guarantees.

## Implementation boundary

This decision defines the target architecture. It does not claim that temporary storage, automatic expiration, or verified deletion has already been implemented.

Implementation must be confirmed through code review and tests.

## Review conditions

Revisit this decision if the product introduces permanent document history, paid persistent storage, organizational workspaces, or different retention requirements.