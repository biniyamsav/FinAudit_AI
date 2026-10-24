import logging
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Workspace
from app.db.session import get_session_factory
from app.retrieval.dense import get_weaviate_client

logger = logging.getLogger(__name__)


def _safe_workspace_id(workspace_id) -> str:
    return str(uuid.UUID(str(workspace_id)))


def delete_workspace_data(workspace_id) -> None:
    wid = _safe_workspace_id(workspace_id)

    # 1. Weaviate objects for this workspace
    client = get_weaviate_client()
    try:
        from weaviate.classes.query import Filter

        collection = client.collections.get("DocumentChunk")
        collection.data.delete_many(
            where=Filter.by_property("workspace_id").equal(wid)
        )
    finally:
        client.close()

    # 2. Temp folder
    path = Path(get_settings().temp_upload_dir) / wid
    try:
        shutil.rmtree(path)
    except FileNotFoundError:
        pass

    # 3. Workspace row (FK cascade)
    factory = get_session_factory()
    with factory() as db:
        workspace = db.get(Workspace, uuid.UUID(wid))
        if workspace is not None:
            db.delete(workspace)
            db.commit()


def cleanup_expired_workspaces() -> int:
    now = datetime.now(timezone.utc)
    factory = get_session_factory()
    deleted = 0
    with factory() as db:
        workspaces = db.scalars(
            select(Workspace).where(
                ((Workspace.status == "active") & (Workspace.expires_at <= now))
                | (Workspace.status == "deleting")
            )
        ).all()
        ids = [w.id for w in workspaces]

    for wid in ids:
        factory2 = get_session_factory()
        with factory2() as db:
            workspace = db.get(Workspace, wid)
            if workspace is None:
                continue
            workspace.status = "deleting"
            db.commit()
        try:
            delete_workspace_data(wid)
            deleted += 1
        except Exception:
            logger.exception("Failed to delete workspace %s", wid)
    return deleted


def _run_loop(stop_event: threading.Event, interval_minutes: int) -> None:
    while not stop_event.wait(interval_minutes * 60):
        try:
            cleanup_expired_workspaces()
        except Exception:
            logger.exception("Scheduled cleanup failed.")


def start_cleanup_thread() -> tuple[threading.Thread, threading.Event]:
    stop_event = threading.Event()
    interval = get_settings().cleanup_interval_minutes
    thread = threading.Thread(
        target=_run_loop, args=(stop_event, interval), daemon=True
    )
    thread.start()
    return thread, stop_event
