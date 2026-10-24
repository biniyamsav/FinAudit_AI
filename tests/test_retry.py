import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Document, IngestionJob, Workspace
from app.db.session import get_db, get_session_factory
from app.main import app
from app.workers import ingestion_worker

client = TestClient(app)


@pytest.fixture(autouse=True)
def stub_process_document(monkeypatch):
    monkeypatch.setattr(ingestion_worker, "process_document", lambda *a, **k: None)
    import app.api.routes.documents as d

    monkeypatch.setattr(d, "process_document", lambda *a, **k: None)


def _make_failed_doc(attempt_count=1, temp_exists=True):
    ws_resp = client.post("/api/v1/workspaces")
    assert ws_resp.status_code == 201
    ws_id = ws_resp.json()["id"]
    up = client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert up.status_code == 201
    doc_id = up.json()["id"]
    factory = get_session_factory()
    with factory() as db:
        doc = db.get(Document, uuid.UUID(doc_id))
        doc.status = "failed"
        job = db.scalars(
            select(IngestionJob)
            .where(IngestionJob.document_id == doc.id)
            .order_by(IngestionJob.created_at.desc())
        ).first()
        job.status = "failed"
        job.attempt_count = attempt_count
        db.commit()
    if not temp_exists:
        path = Path(get_settings().temp_upload_dir) / ws_id / doc_id
        path.unlink(missing_ok=True)
    return ws_id, doc_id


def test_retry_failed_doc():
    ws_id, doc_id = _make_failed_doc()
    r = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/retry")
    assert r.status_code == 202
    assert r.json() == {"id": doc_id, "status": "uploaded"}
    factory = get_session_factory()
    with factory() as db:
        doc = db.get(Document, uuid.UUID(doc_id))
        assert doc.status == "uploaded"
        job = db.scalars(
            select(IngestionJob)
            .where(IngestionJob.document_id == doc.id)
            .order_by(IngestionJob.created_at.desc())
        ).first()
        assert job.status == "queued"


def test_retry_ready_doc_409():
    ws_resp = client.post("/api/v1/workspaces")
    ws_id = ws_resp.json()["id"]
    up = client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    doc_id = up.json()["id"]
    factory = get_session_factory()
    with factory() as db:
        doc = db.get(Document, uuid.UUID(doc_id))
        doc.status = "ready"
        db.commit()
    r = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/retry")
    assert r.status_code == 409


def test_retry_processing_doc_409():
    ws_resp = client.post("/api/v1/workspaces")
    ws_id = ws_resp.json()["id"]
    up = client.post(
        f"/api/v1/workspaces/{ws_id}/documents",
        files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    doc_id = up.json()["id"]
    factory = get_session_factory()
    with factory() as db:
        doc = db.get(Document, uuid.UUID(doc_id))
        doc.status = "processing"
        db.commit()
    r = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/retry")
    assert r.status_code == 409


def test_retry_max_attempts():
    ws_id, doc_id = _make_failed_doc(attempt_count=3)
    r = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/retry")
    assert r.status_code == 409
    assert r.json()["detail"] == "Maximum attempts reached."


def test_retry_temp_missing():
    ws_id, doc_id = _make_failed_doc(temp_exists=False)
    r = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/retry")
    assert r.status_code == 409
    assert r.json()["detail"] == "Original upload is no longer available."


def test_retry_other_workspace_404():
    ws1, doc_id = _make_failed_doc()
    ws2 = client.post("/api/v1/workspaces").json()["id"]
    r = client.post(f"/api/v1/workspaces/{ws2}/documents/{doc_id}/retry")
    assert r.status_code == 404


def test_retry_expired_workspace_404():
    import datetime as dt

    ws_id, doc_id = _make_failed_doc()
    factory = get_session_factory()
    with factory() as db:
        ws = db.get(Workspace, uuid.UUID(ws_id))
        ws.expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)
        db.commit()
    r = client.post(f"/api/v1/workspaces/{ws_id}/documents/{doc_id}/retry")
    assert r.status_code == 404


def test_retry_unknown_doc_404():
    ws_id = client.post("/api/v1/workspaces").json()["id"]
    r = client.post(f"/api/v1/workspaces/{ws_id}/documents/{uuid.uuid4()}/retry")
    assert r.status_code == 404
