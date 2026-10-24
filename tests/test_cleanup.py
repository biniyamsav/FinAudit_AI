import shutil
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.models import Workspace
from app.db.session import get_session_factory
from app.main import app
from app.workers import cleanup as cleanup_mod

client = TestClient(app)


class FakeCollection:
    def __init__(self, raise_for=None):
        self.raise_for = raise_for or set()

    @property
    def data(self):
        return self

    def delete_many(self, where=None):
        # where not inspected; raise based on a global flag set per test
        if getattr(self, "_raise", False):
            raise RuntimeError("weaviate boom")
        return None


class FakeClient:
    def __init__(self):
        self._coll = FakeCollection()
        self.collections = self
        self._raise = False

    def get(self, name):
        self._coll._raise = self._raise
        return self._coll

    def close(self):
        pass


@pytest.fixture(autouse=True)
def clean_db_and_temp():
    factory = get_session_factory()
    with factory() as db:
        db.query(Workspace).delete()
        db.commit()
    tmp = Path(get_settings().temp_upload_dir)
    if tmp.exists():
        for child in tmp.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    yield
    with factory() as db:
        db.query(Workspace).delete()
        db.commit()
    if tmp.exists():
        for child in tmp.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)


@pytest.fixture
def fake_client(monkeypatch):
    fc = FakeClient()
    monkeypatch.setattr(cleanup_mod, "get_weaviate_client", lambda: fc)
    return fc


def _expired_workspace(temp=True):
    ws = client.post("/api/v1/workspaces").json()["id"]
    factory = get_session_factory()
    with factory() as db:
        w = db.get(Workspace, uuid.UUID(ws))
        w.status = "active"
        w.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    if temp:
        p = Path(get_settings().temp_upload_dir) / ws
        p.mkdir(parents=True, exist_ok=True)
        (p / "f.txt").write_text("x")
    return ws


def test_expired_removed(fake_client):
    ws = _expired_workspace()
    n = cleanup_mod.cleanup_expired_workspaces()
    assert n == 1
    factory = get_session_factory()
    with factory() as db:
        assert db.get(Workspace, uuid.UUID(ws)) is None


def test_non_expired_untouched(fake_client):
    ws = client.post("/api/v1/workspaces").json()["id"]
    n = cleanup_mod.cleanup_expired_workspaces()
    assert n == 0
    factory = get_session_factory()
    with factory() as db:
        assert db.get(Workspace, uuid.UUID(ws)) is not None


def test_deleting_picked_up(fake_client):
    ws = _expired_workspace()
    factory = get_session_factory()
    with factory() as db:
        w = db.get(Workspace, uuid.UUID(ws))
        w.status = "deleting"
        db.commit()
    n = cleanup_mod.cleanup_expired_workspaces()
    assert n == 1


def test_weaviate_raises(fake_client, monkeypatch):
    fake_client._raise = True
    ws1 = _expired_workspace()
    ws2 = _expired_workspace()
    n = cleanup_mod.cleanup_expired_workspaces()
    assert n == 0
    factory = get_session_factory()
    with factory() as db:
        for ws in (ws1, ws2):
            w = db.get(Workspace, uuid.UUID(ws))
            assert w is not None and w.status == "deleting"
    for ws in (ws1, ws2):
        assert (Path(get_settings().temp_upload_dir) / ws).exists()


def test_weaviate_raises_first_only(monkeypatch):
    counter = {"n": 0}

    class FC:
        def __init__(self):
            self.collections = self

        def get(self, name):
            return self

        @property
        def data(self):
            return self

        def delete_many(self, where=None):
            counter["n"] += 1
            if counter["n"] == 1:
                raise RuntimeError("weaviate boom")

        def close(self):
            pass

    monkeypatch.setattr(cleanup_mod, "get_weaviate_client", lambda: FC())
    ws1 = _expired_workspace()
    ws2 = _expired_workspace()
    n = cleanup_mod.cleanup_expired_workspaces()
    assert n == 1
    factory = get_session_factory()
    with factory() as db:
        assert db.get(Workspace, uuid.UUID(ws1)) is not None
        assert db.get(Workspace, uuid.UUID(ws2)) is None


def test_second_run_zero(fake_client):
    ws = _expired_workspace()
    assert cleanup_mod.cleanup_expired_workspaces() == 1
    assert cleanup_mod.cleanup_expired_workspaces() == 0


def test_missing_temp_folder(fake_client):
    ws = _expired_workspace(temp=False)
    assert cleanup_mod.cleanup_expired_workspaces() == 1


def test_content_expired_404(fake_client):
    ws = _expired_workspace()
    r = client.get(f"/api/v1/workspaces/{ws}/documents/{uuid.uuid4()}/content")
    assert r.status_code == 404
