"""initial schema

Revision ID: 3a67c317b85c
Revises: 
Create Date: 2026-10-22 10:55:01.366569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a67c317b85c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


STATEMENTS = [
    """CREATE TABLE users (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        email         VARCHAR(255) NOT NULL UNIQUE,
        password_hash VARCHAR(255) NOT NULL,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
    """CREATE TABLE workspaces (
        id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
        status     VARCHAR(30) NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'expired', 'deleting')),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        expires_at TIMESTAMPTZ NOT NULL
    )""",
    "CREATE INDEX ix_workspaces_expires_at ON workspaces(expires_at)",
    "CREATE INDEX ix_workspaces_user_id ON workspaces(user_id)",
    """CREATE TABLE documents (
        id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
        filename     VARCHAR(255) NOT NULL,
        file_type    VARCHAR(100) NOT NULL,
        file_size    BIGINT NOT NULL,
        checksum     VARCHAR(64) NOT NULL,
        status       VARCHAR(30) NOT NULL DEFAULT 'uploaded'
            CHECK (status IN ('uploaded', 'processing', 'ready', 'failed')),
        created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (workspace_id, checksum)
    )""",
    """CREATE TABLE ingestion_jobs (
        id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id   UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
        status        VARCHAR(30) NOT NULL DEFAULT 'queued'
            CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
        error_code    VARCHAR(50),
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
        started_at    TIMESTAMPTZ,
        completed_at  TIMESTAMPTZ
    )""",
    "CREATE INDEX ix_ingestion_jobs_document_id ON ingestion_jobs(document_id)",
    """CREATE TABLE extracted_content (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        document_id UUID NOT NULL UNIQUE REFERENCES documents(id) ON DELETE CASCADE,
        content     JSONB NOT NULL,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    )""",
]


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute(
        "DROP TABLE IF EXISTS ingestion_jobs, extracted_content, "
        "documents, workspaces, users CASCADE"
    )