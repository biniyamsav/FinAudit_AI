
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.core.config import get_settings
from app.db.models import Document, IngestionJob, Workspace
from app.db.session import get_session_factory
from app.main import create_app
from app.workers import ingestion_worker


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _read(document_id: uuid.UUID) -> tuple[str, str, int, str | None]:
    with get_session_factory()() as db:
        document = db.get(Document, document_id)
        job = db.scalars(
            select(IngestionJob).where(IngestionJob.document_id == document_id)
        ).one()
        return document.status, job.status, job.attempt_count, job.error_code


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
            document_id = document.id
        return document_id

    yield _seed

    for path in temp_paths:
        path.unlink(missing_ok=True)
        path.parent.rmdir()
    with get_session_factory()() as db:
        db.execute(delete(Workspace).where(Workspace.id.in_(workspaces)))
        db.commit()


@pytest.fixture
def reprocessed(monkeypatch):
    calls: list[uuid.UUID] = []

    def _fake_process_document(document_id: uuid.UUID) -> None:
        calls.append(document_id)

    monkeypatch.setattr(ingestion_worker, "process_document", _fake_process_document)
    return calls


def test_stale_processing_document_with_temp_file_is_requeued_and_reprocessed(seed, reprocessed):
    document_id = seed(
        document_status="processing",
        job_status="running",
        started_at=_now() - timedelta(minutes=30),
        attempt_count=1,
        with_temp_file=True,
    )

    assert ingestion_worker.recover_stale_documents() == [document_id]
    assert reprocessed == [document_id]
    assert _read(document_id) == ("uploaded", "queued", 1, None)


def test_stale_processing_document_without_temp_file_fails(seed, reprocessed):
    document_id = seed(
        document_status="processing",
        job_status="running",
        started_at=_now() - timedelta(minutes=30),
        attempt_count=1,
    )

    assert ingestion_worker.recover_stale_documents() == []
    assert reprocessed == []
    assert _read(document_id) == ("failed", "failed", 1, "temp_file_missing")


def test_fresh_processing_document_is_untouched(seed, reprocessed):
    document_id = seed(
        document_status="processing",
        job_status="running",
        started_at=_now() - timedelta(minutes=1),
        attempt_count=1,
        with_temp_file=True,
    )

    assert ingestion_worker.recover_stale_documents() == []
    assert reprocessed == []
    assert _read(document_id) == ("processing", "running", 1, None)


def test_processing_document_without_started_at_is_untouched(seed, reprocessed):
    document_id = seed(
        document_status="processing",
        job_status="running",
        started_at=None,
        attempt_count=1,
        with_temp_file=True,
    )

    assert ingestion_worker.recover_stale_documents() == []
    assert reprocessed == []
    assert _read(document_id) == ("processing", "running", 1, None)


def test_ready_and_failed_documents_are_untouched(seed, reprocessed):
    ready_id = seed(
        document_status="ready",
        job_status="succeeded",
        started_at=_now() - timedelta(minutes=30),
        attempt_count=1,
    )
    failed_id = seed(
        document_status="failed",
        job_status="failed",
        started_at=_now() - timedelta(minutes=30),
        attempt_count=1,
        error_code="extraction_failed",
    )

    assert ingestion_worker.recover_stale_documents() == []
    assert reprocessed == []
    assert _read(ready_id) == ("ready", "succeeded", 1, None)
    assert _read(failed_id) == ("failed", "failed", 1, "extraction_failed")


def test_stale_document_at_max_attempts_is_failed_without_requeue(seed, reprocessed):
    document_id = seed(
        document_status="processing",
        job_status="running",
        started_at=_now() - timedelta(minutes=30),
        attempt_count=3,
        with_temp_file=True,
    )

    assert ingestion_worker.recover_stale_documents() == []
    assert reprocessed == []
    assert _read(document_id) == ("failed", "failed", 3, "max_attempts_exceeded")


def test_recovery_failure_does_not_stop_app_startup(monkeypatch):
    def _boom() -> list[uuid.UUID]:
        raise RuntimeError("recovery failed")

    monkeypatch.setattr("app.main.recover_stale_documents", _boom)

    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health").status_code == 200
