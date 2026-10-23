import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Document, ExtractedContent, IngestionJob
from app.db.session import get_session_factory
from app.ingestion.common import ExtractionError
from app.ingestion.csv_text import extract_csv
from app.ingestion.docx_text import extract_docx
from app.ingestion.excel import extract_xls, extract_xlsx
from app.ingestion.ocr import extract_ocr
from app.ingestion.pdf_text import extract_pdf_text

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
            extracted = extractor(path)
            db.add(
                ExtractedContent(
                    document_id=document.id, content=extracted.model_dump()
                )
            )
            document.status = "ready"
            job.status = "succeeded"
            job.completed_at = _now()
            db.commit()
        except Exception as error:
            db.rollback()
            job.status = "failed"
            job.error_code = (
                error.code
                if isinstance(error, ExtractionError)
                else "extraction_failed"
            )
            job.completed_at = _now()
            document.status = "failed"
            db.commit()
            return

        path.unlink(missing_ok=True)
