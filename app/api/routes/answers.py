"""Chat endpoint: hybrid retrieval -> grounded context -> Groq -> persist."""

import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, Workspace
from app.db.session import get_db
from app.llm.protocol import LLMError, LLMProviderProtocol
from app.llm.providers.groq_provider import GroqLLMProvider
from app.retrieval.context_builder import _coerce_provenance, build_rag_context
from app.retrieval.dense import get_weaviate_client
from app.retrieval.embeddings import embed_text
from app.retrieval.fusion import hybrid_search
from app.retrieval.reranking import rerank_chunks
from app.storage.conversations import save_conversation_message

router = APIRouter(prefix="/workspaces/{workspace_id}/chat", tags=["chat"])

# The model is a narrator over retrieved evidence, never the source of a
# number: withholding invented figures matters more than sounding complete
# when the output is an audit finding.
SYSTEM_PROMPT = (
    "You are an audit reviewer for FinAudit_AI. Answer using ONLY the "
    "financial records provided in the context. Cite the source (document, "
    "page, table or sheet) for every figure you quote. If the context does "
    "not contain the answer, say so plainly -- never invent amounts, "
    "account codes, dates or totals."
)


class ChatRequest(BaseModel):
    """Inbound chat payload."""

    query: str = Field(min_length=1, max_length=4000)
    limit: int = Field(default=5, ge=1, le=20)


class Citation(BaseModel):
    """One grounding source, detailed enough for a reviewer to open the file
    and land on the exact page, table or sheet behind a figure."""

    chunk_id: str | None = None
    document_id: str | None = None
    document_name: str | None = None
    page_number: int | None = None
    table_index: int | None = None
    sheet_name: str | None = None
    score: float | None = None


class ChatResponse(BaseModel):
    """Outbound chat payload."""

    answer: str
    citations: list[Citation]
    conversation_message_id: uuid.UUID


def get_llm_provider_factory() -> Callable[[], LLMProviderProtocol]:
    """Return the configured provider *constructor*.

    Deliberately a factory rather than a provider: FastAPI resolves
    dependencies before the handler runs, and constructing GroqLLMProvider
    validates ``GROQ_API_KEY``.  Building it eagerly would make a request for
    a non-existent workspace report ``503 missing API key`` instead of the
    ``404`` it deserves.  Constructing after validation keeps the error order
    correct, while still letting tests swap in a stub.
    """
    return GroqLLMProvider


def _active_workspace(db: Session, workspace_id: uuid.UUID) -> Workspace:
    """Load a workspace or raise 404 -- the same rule documents.py applies."""
    workspace = db.get(Workspace, workspace_id)
    if (
        workspace is None
        or workspace.status != "active"
        or workspace.expires_at <= datetime.now(timezone.utc)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workspace not found."
        )
    return workspace


def _document_names(
    db: Session, workspace_id: uuid.UUID, document_ids: set[str]
) -> dict[str, str]:
    """Map document id -> filename for citation display.

    Filtered by ``workspace_id`` as well as by id: chunk ids arrive from the
    retrieval layer, so a stray or tampered id must not be able to pull a
    filename out of another tenant's workspace.
    """
    uuids: list[uuid.UUID] = []
    for raw in document_ids:
        try:
            uuids.append(uuid.UUID(raw))
        except (ValueError, AttributeError, TypeError):
            continue
    if not uuids:
        return {}

    rows = db.scalars(
        select(Document).where(
            Document.workspace_id == workspace_id, Document.id.in_(uuids)
        )
    )
    return {str(row.id): row.filename for row in rows}


@router.post("", response_model=ChatResponse)
def create_chat(
    workspace_id: uuid.UUID,
    request: Request,
    payload: ChatRequest,
    db: Annotated[Session, Depends(get_db)],
    provider_factory: Annotated[
        Callable[[], LLMProviderProtocol], Depends(get_llm_provider_factory)
    ],
) -> ChatResponse:
    """Answer a question about a workspace's documents, with citations.

    Pipeline: validate workspace -> hybrid search (workspace-scoped) ->
    rerank/dedupe -> assemble cited context -> Groq -> persist the exchange.
    """
    from app.core.config import get_settings
    from app.core.rate_limit import check_rate_limit

    settings = get_settings()
    client_ip = request.client.host if request.client else "unknown"
    retry_after = check_rate_limit(
        f"chat:{workspace_id}:{client_ip}", settings.chat_rate_limit_per_minute
    )
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests.",
            headers={"Retry-After": str(retry_after)},
        )

    _active_workspace(db, workspace_id)

    has_document = db.scalars(
        select(Document.id)
        .where(Document.workspace_id == workspace_id)
        .limit(1)
    ).first()
    if has_document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No documents found in this workspace.",
        )

    query_vector = embed_text(payload.query)
    try:
        client = get_weaviate_client()
        try:
            candidates = hybrid_search(
                client,
                str(workspace_id),
                payload.query,
                query_vector,
                limit=payload.limit,
            )
        finally:
            client.close()
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document retrieval is unavailable.",
        ) from error

    ranked = rerank_chunks(candidates, top_k=payload.limit)

    names = _document_names(db, workspace_id, {c.get("document_id") for c in ranked})
    citations: list[Citation] = []
    for chunk in ranked:
        provenance = _coerce_provenance(chunk.get("provenance"))
        document_id = chunk.get("document_id")
        citations.append(
            Citation(
                chunk_id=chunk.get("chunk_id"),
                document_id=document_id,
                document_name=names.get(document_id),
                page_number=provenance.get("page"),
                table_index=provenance.get("table_index"),
                sheet_name=provenance.get("sheet"),
                score=chunk.get("score"),
            )
        )

    context = build_rag_context(ranked)
    user_prompt = f"{context}\n\n## Question\n{payload.query}"

    try:
        llm = provider_factory()
    except LLMError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)
        ) from error

    try:
        answer = llm.generate(SYSTEM_PROMPT, user_prompt)
    except LLMError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The language model failed to produce an answer.",
        ) from error

    message = save_conversation_message(
        db,
        workspace_id=workspace_id,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response=answer,
        cited_chunk_ids=[c.chunk_id for c in citations if c.chunk_id],
    )

    return ChatResponse(
        answer=answer,
        citations=citations,
        conversation_message_id=message.id,
    )
