"""Persistence for chat exchanges.

Thin storage boundary: the route owns request/response concerns, this layer
owns SQL.  Every read/write is scoped to ``workspace_id`` so a message can
never be written against -- or later surfaced from -- another tenant's
workspace.
"""

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import ConversationMessage


def save_conversation_message(
    db: Session,
    *,
    workspace_id: uuid.UUID,
    system_prompt: str,
    user_prompt: str,
    response: str,
    cited_chunk_ids: Sequence[Any],
) -> ConversationMessage:
    """Persist one chat exchange and return the stored row.

    ``cited_chunk_ids`` is stored as-is in a JSONB column: it is the join
    between an answer and the specific retrieved chunks that grounded it, so
    a reviewer can trace the answer back to document provenance.  Callers
    are responsible for having validated the workspace; the foreign key still
    rejects a dangling id.
    """
    message = ConversationMessage(
        workspace_id=workspace_id,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response=response,
        cited_chunk_ids=list(cited_chunk_ids),
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message
