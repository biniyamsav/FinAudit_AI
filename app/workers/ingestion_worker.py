import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Document, ExtractedContent, IngestionJob
from app.db.session import get_session_factory
from app.ingestion.chunking import chunk_document
from app.ingestion.common import ExtractionError
from app.ingestion.csv_text import extract_csv
from app.ingestion.docx_text import extract_docx
from app.ingestion.excel import extract_xls, extract_xlsx
from app.ingestion.ocr import extract_ocr
from app.ingestion.pdf_text import extract_pdf_text
from app.retrieval.dense import get_weaviate_client, store_chunks_in_weaviate

EXTRACTORS = {
    ".pdf": extract_pdf_text,
    ".xlsx": extract_xlsx,
    ".xls": extract_xls,
    ".csv": extract_csv,
    ".docx": extract_docx,
    ".png": extract_ocr,
    ".jpg": extract_ocr,
    ".jpeg": extract_ocr,
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


class VectorIndexError(RuntimeError):
    """Raised when extracted chunks could not be indexed for retrieval."""


def _error_code(error: Exception) -> str:
    """Map a failure onto the job's stable error code.

    Extraction and indexing fail for different reasons and need different
    responses: a malformed document needs a new file, a vector-store outage
    needs an operator.
    """
    if isinstance(error, ExtractionError):
        return error.code
    if isinstance(error, VectorIndexError):
        return "vector_store_failed"
    return "extraction_failed"


def _index_chunks(document: Document, content: dict) -> None:
    """Chunk extracted content and write it to Weaviate with embeddings.

    An empty chunk list is not an error: it means the chunker has no branch
    for this file type (standalone images), and extraction itself succeeded.
    """
    chunks = chunk_document(
        document_id=str(document.id),
        workspace_id=str(document.workspace_id),
        file_type=Path(document.filename).suffix.lower(),
        content=content,
    )
    if not chunks:
        return

    try:
        client = get_weaviate_client()
        try:
            store_chunks_in_weaviate(client, chunks)
        finally:
            client.close()
    except Exception as error:
        raise VectorIndexError(str(error)) from error


def process_document(document_id: uuid.UUID) -> None:
    with get_session_factory()() as db:
        document = db.get(Document, document_id)
        job = db.scalars(
            select(IngestionJob)
            .where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.created_at.desc())
        ).first()
        if document is None or job is None:
            return
        if document.status in ("processing", "ready"):
            return

        path = (
            Path(get_settings().temp_upload_dir)
            / str(document.workspace_id)
            / str(document.id)
        )

        job.status = "running"
        job.attempt_count += 1
        job.started_at = _now()
        document.status = "processing"
        db.commit()

        try:
            extractor = EXTRACTORS.get(Path(document.filename).suffix.lower())
            if extractor is None:
                raise ExtractionError("unsupported_type")
            timeout = get_settings().extraction_timeout_seconds
            # Python cannot kill a hung thread; we only stop waiting for it.
            # The thread may keep running in the background.
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(extractor, path)
                try:
                    extracted = future.result(timeout=timeout)
                except FutureTimeoutError:
                    job.status = "failed"
                    job.error_code = "extraction_timeout"
                    job.completed_at = _now()
                    document.status = "failed"
                    db.commit()
                    return
            content = extracted.model_dump()

            # Index before committing so "ready" always implies
            # "searchable": a Weaviate outage must fail the job instead of
            # leaving a document that chat silently cannot find.
            _index_chunks(document, content)

            db.add(ExtractedContent(document_id=document.id, content=content))
            document.status = "ready"
            job.status = "succeeded"
            job.completed_at = _now()
            db.commit()
        except Exception as error:
            db.rollback()
            job.status = "failed"
            job.error_code = _error_code(error)
            job.completed_at = _now()
            document.status = "failed"
            db.commit()
            return

        path.unlink(missing_ok=True)


def recover_stale_documents() -> list[uuid.UUID]:
    """Requeue documents a dead worker left in "processing"."""

    settings = get_settings()
    threshold = _now() - timedelta(minutes=settings.processing_stale_minutes)
    requeued: list[uuid.UUID] = []

    with get_session_factory()() as db:
        documents = db.scalars(
            select(Document).where(Document.status == "processing")
        ).all()

        for document in documents:
            job = db.scalars(
                select(IngestionJob)
                .where(IngestionJob.document_id == document.id)
                .order_by(IngestionJob.created_at.desc())
            ).first()
            if job is None or job.started_at is None or job.started_at > threshold:
                continue

            path = (
                Path(settings.temp_upload_dir)
                / str(document.workspace_id)
                / str(document.id)
            )

            if job.attempt_count >= 3:
                document.status = "failed"
                job.status = "failed"
                job.error_code = "max_attempts_exceeded"
                db.commit()
            elif not path.exists():
                document.status = "failed"
                job.status = "failed"
                job.error_code = "temp_file_missing"
                db.commit()
            else:
                document.status = "uploaded"
                job.status = "queued"
                job.error_code = None
                db.commit()
                requeued.append(document.id)

    for document_id in requeued:
        process_document(document_id)

    return requeued
