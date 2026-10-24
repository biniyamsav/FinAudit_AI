import time
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.api.routes import documents as docs_mod
from app.db.session import get_session_factory
from app.db.models import Document
from app.main import app
from app.workers import ingestion_worker
from sqlalchemy import select
from app.db.models import IngestionJob
from app.core.rate_limit import reset_rate_limits

client = TestClient(app)
REAL_PROCESS_DOCUMENT = ingestion_worker.process_document


@pytest.fixture(autouse=True)
def reset_state(monkeypatch):
    get_settings.cache_clear()
    reset_rate_limits()
    monkeypatch.setattr(ingestion_worker, "process_document", lambda *a, **k: None)
    import app.api.routes.documents as d

    monkeypatch.setattr(d, "process_document", lambda *a, **k: None)
    yield
    get_settings.cache_clear()
    reset_rate_limits()


def _ws():
    return client.post("/api/v1/workspaces").json()["id"]


def test_doc_limit(monkeypatch):
    ws = _ws()
    import app.api.routes.documents as d

    class S:
        max_documents_per_workspace = 20
        max_workspace_bytes = 200_000_000
        temp_upload_dir = get_settings().temp_upload_dir
        upload_rate_limit_per_minute = 1000

    monkeypatch.setattr(docs_mod, "get_settings", lambda: S())
    for i in range(20):
        r = client.post(
            f"/api/v1/workspaces/{ws}/documents",
            files={"file": (f"a{i}.pdf", (b"%PDF-1.4 " + str(i).encode()), "application/pdf")},
        )
        assert r.status_code in (200, 201)
    r = client.post(
        f"/api/v1/workspaces/{ws}/documents",
        files={"file": ("a20.pdf", b"%PDF-1.4 20", "application/pdf")},
    )
    assert r.status_code == 409
    assert r.json()["detail"] == "Document limit reached."


def test_byte_quota():
    ws = _ws()
    # fill with one big-ish? Instead set max_workspace_bytes low via env not possible; use monkeypatch settings
    get_settings.cache_clear()
    from app.core.config import Settings

    # override by monkeypatching get_settings in documents module
    import app.api.routes.documents as d

    orig = d.get_settings

    class S:
        max_documents_per_workspace = 20
        max_workspace_bytes = 10
        temp_upload_dir = get_settings().temp_upload_dir
        upload_rate_limit_per_minute = 20

    d.get_settings = lambda: S()
    try:
        r = client.post(
            f"/api/v1/workspaces/{ws}/documents",
            files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        assert r.status_code == 413
        assert r.json()["detail"] == "Workspace storage limit reached."
        folder = Path(get_settings().temp_upload_dir) / ws
        leftovers = list(folder.iterdir()) if folder.exists() else []
        assert leftovers == []
    finally:
        d.get_settings = orig
        get_settings.cache_clear()


def test_rate_limit():
    ws = _ws()
    statuses = []
    for i in range(21):
        r = client.post(
            f"/api/v1/workspaces/{ws}/documents",
            files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        statuses.append(r.status_code)
    assert 429 in statuses
    # find a 429 response
    for i in range(21):
        r = client.post(
            f"/api/v1/workspaces/{ws}/documents",
            files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
        )
        if r.status_code == 429:
            assert "Retry-After" in r.headers
            break


def test_extraction_timeout(monkeypatch):
    monkeypatch.setenv("EXTRACTION_TIMEOUT_SECONDS", "1")
    get_settings.cache_clear()

    def sleepy(path):
        time.sleep(5)

    monkeypatch.setitem(ingestion_worker.EXTRACTORS, ".pdf", sleepy)
    monkeypatch.setattr(ingestion_worker, "process_document", REAL_PROCESS_DOCUMENT)
    monkeypatch.setattr(docs_mod, "process_document", REAL_PROCESS_DOCUMENT)

    ws = _ws()
    r = client.post(
        f"/api/v1/workspaces/{ws}/documents",
        files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert r.status_code == 201
    doc_id = r.json()["id"]

    with get_session_factory()() as db:
        doc = db.get(Document, uuid.UUID(doc_id))
        job = db.scalars(
            select(IngestionJob)
            .where(IngestionJob.document_id == doc.id)
            .order_by(IngestionJob.created_at.desc())
        ).first()
        assert doc.status == "failed"
        assert job.error_code == "extraction_timeout"

    assert (Path(get_settings().temp_upload_dir) / ws / doc_id).exists()


def test_normal_upload():
    ws = _ws()
    r = client.post(
        f"/api/v1/workspaces/{ws}/documents",
        files={"file": ("a.pdf", b"%PDF-1.4 test", "application/pdf")},
    )
    assert r.status_code == 201
