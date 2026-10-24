import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.routes.answers import get_llm_provider_factory
from app.db.models import ConversationMessage, Document
from app.db.session import get_session_factory
from app.llm.protocol import LLMError
from app.main import app
from tests.test_worker import make_pdf

client = TestClient(app)


class StubLLM:
    """Deterministic stand-in so no test needs a key or network."""

    def __init__(self, answer: str = "Gross revenue was 1500 USD.", error: Exception | None = None):
        self.answer = answer
        self.error = error
        self.calls: list[tuple[str, str, float]] = []

    def generate(self, system_prompt: str, user_prompt: str, temperature: float = 0.0) -> str:
        self.calls.append((system_prompt, user_prompt, temperature))
        if self.error is not None:
            raise self.error
        return self.answer


@pytest.fixture(autouse=True)
def _clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()


def _use(stub: StubLLM) -> None:
    # The dependency returns the constructor; the handler then calls it.
    app.dependency_overrides[get_llm_provider_factory] = lambda: (lambda: stub)


def _workspace_with_pdf(text: str = "Revenue 1500") -> str:
    workspace_id = client.post("/api/v1/workspaces").json()["id"]
    files = {"file": ("annual_report.pdf", make_pdf(text), "application/pdf")}
    response = client.post(f"/api/v1/workspaces/{workspace_id}/documents", files=files)
    assert response.status_code == 201, response.text
    return workspace_id


def _chat(workspace_id: str, payload: dict):
    return client.post(f"/api/v1/workspaces/{workspace_id}/chat", json=payload)


def test_chat_returns_answer_citations_and_message_id():
    stub = StubLLM()
    _use(stub)
    workspace_id = _workspace_with_pdf()

    response = _chat(workspace_id, {"query": "What was the revenue?"})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["answer"] == "Gross revenue was 1500 USD."
    assert isinstance(body["conversation_message_id"], str)
    uuid.UUID(body["conversation_message_id"])  # parses as a uuid

    assert body["citations"], "a document was uploaded, so a cite is expected"
    citation = body["citations"][0]
    assert citation["document_name"] == "annual_report.pdf"
    assert citation["page_number"] == 1
    assert citation["score"] is not None
    assert citation["chunk_id"]
    assert citation["document_id"]


def test_chat_context_carries_provenance_and_uses_deterministic_temperature():
    stub = StubLLM()
    _use(stub)
    workspace_id = _workspace_with_pdf()

    _chat(workspace_id, {"query": "What was the revenue?"})

    system_prompt, user_prompt, temperature = stub.calls[0]
    assert temperature == 0.0
    assert "audit reviewer" in system_prompt.lower()
    assert "Page 1" in user_prompt          # provenance header in context
    assert "**Document ID:**" in user_prompt  # required provenance header
    assert "What was the revenue?" in user_prompt  # the actual question


def test_chat_persists_prompt_response_and_cited_chunk_ids():
    stub = StubLLM()
    _use(stub)
    workspace_id = _workspace_with_pdf()

    body = _chat(workspace_id, {"query": "What was the revenue?"}).json()
    message_id = uuid.UUID(body["conversation_message_id"])

    with get_session_factory()() as db:
        row = db.get(ConversationMessage, message_id)
        assert row is not None
        assert row.workspace_id == uuid.UUID(workspace_id)
        assert "What was the revenue?" in row.user_prompt
        assert row.response == "Gross revenue was 1500 USD."
        assert row.system_prompt.strip()
        assert row.cited_chunk_ids == [c["chunk_id"] for c in body["citations"]]


def test_chat_only_cites_documents_belonging_to_the_workspace():
    _use(StubLLM())
    workspace_id = _workspace_with_pdf()

    body = _chat(workspace_id, {"query": "revenue"}).json()
    with get_session_factory()() as db:
        owned = {
            str(row.id)
            for row in db.scalars(
                select(Document).where(Document.workspace_id == uuid.UUID(workspace_id))
            )
        }
    cited = {c["document_id"] for c in body["citations"]}
    assert cited <= owned, f"cited {cited - owned} from outside the workspace"


def test_chat_unknown_workspace_returns_404():
    _use(StubLLM())
    response = _chat("00000000-0000-0000-0000-000000000000", {"query": "revenue"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Workspace not found."


def test_chat_without_documents_returns_404():
    _use(StubLLM())
    workspace_id = client.post("/api/v1/workspaces").json()["id"]
    response = _chat(workspace_id, {"query": "revenue"})
    assert response.status_code == 404
    assert "documents" in response.json()["detail"].lower()


def test_chat_malformed_workspace_id_returns_422():
    _use(StubLLM())
    response = _chat("not-a-uuid", {"query": "revenue"})
    assert response.status_code == 422


def test_chat_llm_failure_returns_502_and_does_not_persist():
    _use(StubLLM(error=LLMError("provider blew up")))
    workspace_id = _workspace_with_pdf()

    with get_session_factory()() as db:
        before = len(
            list(db.scalars(select(ConversationMessage)))
        )

    response = _chat(workspace_id, {"query": "revenue"})
    assert response.status_code == 502

    with get_session_factory()() as db:
        after = len(list(db.scalars(select(ConversationMessage))))
    assert after == before, "a failed answer must not be stored as a message"


def test_chat_missing_api_key_returns_503(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    workspace_id = _workspace_with_pdf()
    response = _chat(workspace_id, {"query": "revenue"})
    assert response.status_code == 503
    assert "GROQ_API_KEY" in response.json()["detail"]
    assert "gsk" not in response.json()["detail"]  # never echo a credential


def test_chat_rejects_empty_and_oversized_queries():
    _use(StubLLM())
    workspace_id = _workspace_with_pdf()
    assert _chat(workspace_id, {"query": ""}).status_code == 422
    assert _chat(workspace_id, {"query": "x" * 5000}).status_code == 422
    assert _chat(workspace_id, {"limit": 99}).status_code == 422
