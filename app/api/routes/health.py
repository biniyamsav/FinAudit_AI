"""Health endpoints.

``/health`` is a *liveness* probe: it must stay cheap and answer ``200`` with
``{"status": "ok"}`` regardless of backing services -- its exact payload is
already relied upon by clients and tests.

``/health/status`` is the *readiness* view a frontend polls to show whether
PostgreSQL, Weaviate and Groq are usable.  Failures are reported as data
(status + exception type name), never raw exception text or connection
strings, so a health endpoint cannot leak credentials.
"""

import os

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.db.session import get_session_factory
from app.llm.providers.groq_provider import DEFAULT_MODEL, GROQ_BASE_URL
from app.retrieval.dense import get_weaviate_client

router = APIRouter()


class HealthResponse(BaseModel):
    status: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Liveness only -- unchanged, deliberately dependency-free."""
    return HealthResponse(status="ok")


class DependencyStatus(BaseModel):
    name: str
    status: str
    detail: str | None = None


class SystemStatusResponse(BaseModel):
    status: str
    dependencies: list[DependencyStatus]


def _postgres_status() -> DependencyStatus:
    try:
        with get_session_factory()() as db:
            db.execute(text("SELECT 1"))
    except Exception as error:
        # Exception type only: the message can embed the connection URL.
        return DependencyStatus(
            name="postgresql", status="error", detail=type(error).__name__
        )
    return DependencyStatus(name="postgresql", status="ok")


def _weaviate_status() -> DependencyStatus:
    try:
        client = get_weaviate_client()
        try:
            ready = client.is_ready()
        finally:
            client.close()
    except Exception as error:
        return DependencyStatus(
            name="weaviate", status="error", detail=type(error).__name__
        )
    if not ready:
        return DependencyStatus(name="weaviate", status="error", detail="not_ready")
    return DependencyStatus(name="weaviate", status="ok")


def _groq_status() -> DependencyStatus:
    """Report Groq *configuration*, not a live round trip.

    A health probe is polled often; pinging a paid API on every request
    would burn quota and make status flaky.  Callers can tell "configured"
    from "reachable" -- this is explicitly not a connectivity claim.
    """
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        return DependencyStatus(
            name="groq",
            status="not_configured",
            detail="GROQ_API_KEY is not set",
        )
    return DependencyStatus(
        name="groq",
        status="configured",
        detail=f"model={os.environ.get('LLM_MODEL') or DEFAULT_MODEL} base_url={GROQ_BASE_URL}",
    )


@router.get("/health/status", response_model=SystemStatusResponse)
def system_status() -> SystemStatusResponse:
    """Dependency readiness for PostgreSQL, Weaviate and Groq."""
    dependencies = [_postgres_status(), _weaviate_status(), _groq_status()]

    # Only hard dependencies degrade readiness: an unconfigured Groq key is a
    # valid state while the mock provider is in use.
    blocking = [d for d in dependencies if d.status == "error"]
    return SystemStatusResponse(
        status="degraded" if blocking else "ok",
        dependencies=dependencies,
    )
