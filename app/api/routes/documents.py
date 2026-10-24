import time
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.db.models import Document, ExtractedContent, IngestionJob, Workspace

from sqlalchemy.exc import IntegrityError
from app.core.config import get_settings
from app.db.models import Document, IngestionJob, Workspace
from app.db.session import get_db
from app.workers.ingestion_worker import process_document


_rate_limit_lock = threading.Lock()
_rate_limit_buckets: dict = {}


def _check_rate_limit(key: str, limit: int) -> int | None:
    now = time.time()
    window = 60.0
    with _rate_limit_lock:
        bucket = _rate_limit_buckets.setdefault(key, [])
        bucket[:] = [t for t in bucket if now - t < window]
        if len(bucket) >= limit:
            retry_after = int(window - (now - bucket[0])) + 1
            return max(1, retry_after)
        bucket.append(now)
        return None
router = APIRouter(
    prefix="/workspaces/{workspace_id}/documents",
    tags=["documents"],
)

ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".xlsx", ".xls", ".csv",
    ".png", ".jpg", ".jpeg",
}

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
CHUNK_SIZE = 1024 * 1024

SIGNATURES = {
    ".pdf": b"%PDF-",
    ".docx": b"PK\x03\x04",
    ".xlsx": b"PK\x03\x04",
    ".xls": b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
    ".png": b"\x89PNG\r\n\x1a\n",
    ".jpg": b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
}


def has_valid_signature(path: Path, extension: str) -> bool:
    with path.open("rb") as f:
        head = f.read(16)

    if extension == ".csv":
        return b"\x00" not in head

    return head.startswith(SIGNATURES[extension])


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    filename: str
    file_type: str
    file_size: int
    checksum: str
    status: str
    created_at: datetime


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_document(
    workspace_id: uuid.UUID,
    file: UploadFile,
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
) -> Document:
    workspace = db.get(Workspace, workspace_id)

    if (
        workspace is None
        or workspace.status != "active"
        or workspace.expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    retry_after = _check_rate_limit(
        f"{workspace_id}:{client_ip}", settings.upload_rate_limit_per_minute
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests.",
            headers={"Retry-After": str(retry_after)},
        )

    count = db.scalar(
        select(func.count()).select_from(Document).where(
            Document.workspace_id == workspace_id
        )
    )
    if count is not None and count >= settings.max_documents_per_workspace:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document limit reached.",
        )

    filename = Path(file.filename or "").name
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported file type.",
        )

    document_id = uuid.uuid4()
    folder = Path(get_settings().temp_upload_dir) / str(workspace_id)
    folder.mkdir(parents=True, exist_ok=True)

    path = folder / str(document_id)

    sha = hashlib.sha256()
    size = 0

    try:
        with path.open("wb") as out:
            while chunk := file.file.read(CHUNK_SIZE):
                size += len(chunk)

                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="File too large.",
                    )

                sha.update(chunk)
                out.write(chunk)

        if size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty.",
            )

        if not has_valid_signature(path, extension):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail="File content does not match its type.",
            )

    except Exception:
        path.unlink(missing_ok=True)
        raise

    checksum = sha.hexdigest()

    existing_size = db.scalar(
        select(func.coalesce(func.sum(Document.file_size), 0)).where(
            Document.workspace_id == workspace_id
        )
    ) or 0
    if existing_size + size > settings.max_workspace_bytes:
        path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Workspace storage limit reached.",
        )

    existing = db.scalars(
        select(Document).where(
            Document.workspace_id == workspace_id,
            Document.checksum == checksum,
        )
    ).first()

    if existing is not None:
        path.unlink(missing_ok=True)
        response.status_code = status.HTTP_200_OK
        return existing

    try:
        document = Document(
            id=document_id,
            workspace_id=workspace_id,
            filename=filename[:255],
            file_type=(
                file.content_type or "application/octet-stream"
            )[:100],
            file_size=size,
            checksum=checksum,
        )

        db.add(document)
        db.flush()

        db.add(IngestionJob(document_id=document_id))

        db.commit()

    except IntegrityError:
        db.rollback()
        path.unlink(missing_ok=True)
        existing = db.scalars(
            select(Document).where(
                Document.workspace_id == workspace_id,
                Document.checksum == checksum,
            )
        ).first()
        if existing is None:
            raise
        response.status_code = status.HTTP_200_OK
        return existing

    except Exception:
        db.rollback()
        path.unlink(missing_ok=True)
        raise

    db.refresh(document)
    background_tasks.add_task(process_document, document.id)
    return document

@router.post(
    "/{document_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_document(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    workspace = db.get(Workspace, workspace_id)

    if (
        workspace is None
        or workspace.status != "active"
        or workspace.expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )

    document = db.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    if document.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document is not in a failed state.",
        )

    job = db.scalars(
        select(IngestionJob)
        .where(IngestionJob.document_id == document_id)
        .order_by(IngestionJob.created_at.desc())
    ).first()

    if job is not None and job.attempt_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum attempts reached.",
        )

    path = (
        Path(get_settings().temp_upload_dir)
        / str(workspace_id)
        / str(document_id)
    )
    if not path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Original upload is no longer available.",
        )

    document.status = "uploaded"
    if job is not None:
        job.status = "queued"
        job.error_code = None
        job.completed_at = None
    db.commit()

    background_tasks.add_task(process_document, document.id)
    return {"id": str(document.id), "status": "uploaded"}


@router.get("/{document_id}/content")
def get_document_content(
    workspace_id: uuid.UUID,
    document_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    workspace = db.get(Workspace, workspace_id)
    if (
        workspace is None
        or workspace.status != "active"
        or workspace.expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found.",
        )
    document = db.get(Document, document_id)
    if document is None or document.workspace_id != workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found.")
    if document.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, f"Document is {document.status}.")
    row = db.scalars(
        select(ExtractedContent).where(ExtractedContent.document_id == document_id)
    ).one()
    return row.content