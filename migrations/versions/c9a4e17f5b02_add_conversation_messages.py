"""add conversation messages

Revision ID: c9a4e17f5b02
Revises: 3a67c317b85c
Create Date: 2026-10-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c9a4e17f5b02'
down_revision: Union[str, Sequence[str], None] = '3a67c317b85c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATEMENTS = [
    """CREATE TABLE conversation_messages (
        id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id    UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        system_prompt   TEXT NOT NULL,
        user_prompt     TEXT NOT NULL,
        response        TEXT NOT NULL,
        cited_chunk_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
        created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    (
        "CREATE INDEX ix_conversation_messages_workspace_id "
        "ON conversation_messages(workspace_id)"
    ),
]


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conversation_messages CASCADE")
