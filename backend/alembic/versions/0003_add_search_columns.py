"""add embeddings and full-text search

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.add_column("chunks", sa.Column("embedding", Vector(384), nullable=True))
    op.add_column("documents", sa.Column("embedding_model", sa.String(length=100), nullable=True))

    # PostgreSQL recomputes this itself whenever `content` changes.
    op.execute(
        "ALTER TABLE chunks ADD COLUMN search_vector tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.execute("CREATE INDEX ix_chunks_search_vector ON chunks USING GIN (search_vector)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_search_vector")
    op.execute("ALTER TABLE chunks DROP COLUMN IF EXISTS search_vector")
    op.drop_column("documents", "embedding_model")
    op.drop_column("chunks", "embedding")
