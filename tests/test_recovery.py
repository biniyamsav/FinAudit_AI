
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.core.config import get_settings
from app.db.models import Document, IngestionJob, Workspace
from app.db.session import get_session_factory
from app.main import create_app
from app.workers import ingestion_worker


def _now() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def pinned_stale_window(monkeypatch):
    monkeypatch.setenv("PROCESSING_STALE_MINUTES", "15")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def seed():
    workspaces: list[uuid.UUID] = []
    temp_paths: list[Path] = []

    def _seed(
        *,
        document_status: str,
        job_status: str,
        started_at: datetime | None,
        attempt_count: int,
        error_code: str | None = None,
        with_temp_file: bool = False,
    ):
        with get_session_factory()() as db:
            workspace = Workspace(expires_at=_now() + timedelta(hours=1))
            db.add(workspace)
            db.flush()
            document = Document(
                workspace_id=workspace.id,
                filename="revenue.pdf",
                file_type="pdf",
                file_size=12,
                checksum=uuid.uuid4().hex,
                status=document_status,
            )
            db.add(document)
            db.flush()
            db.add(
                IngestionJob(
                    document_id=document.id,
                    status=job_status,
                    attempt_count=attempt_count,
                    error_code=error_code,
                    started_at=started_at,
                )
            )
            db.commit()

            path = (
                Path(get_settings().temp_upload_dir)
                / str(workspace.id)
                / str(document.id)
            )
            if with_temp_file:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"revenue")
                temp_paths.append(path)
            workspaces.append(workspace.id)
            return document.id

    yield _seed

    for path in temp_paths:
        path.unlink(missing_ok=True)
        path.parent.rmdir()
    with get_session_factory()() as db:
        db.execute(delete(Workspace).where(Workspace.id.in_(workspaces)))
        db.commit()


@pytest.fixture
def recorder(monkeypatch):
    calls: list[uuid.UUID] = []

    def _fake_process_document(document_id: uuid.UUID) -> None:
        calls.append(document_id)

    monkeypatch.setattr(
        ingestion_worker, "process_document", _fake_process_document
    )
    return calls


def read(document_id: uuid.UUID) -> tuple[str, str, int, str | None]:
    with get_session_factory()() as db:
        document = db.get(Document, document_id)
        job = db.scalars(
            delete().where  # placeholder
        ).first() if False else None
        return document.status, job.status, job.attempt_count, job.error_code
