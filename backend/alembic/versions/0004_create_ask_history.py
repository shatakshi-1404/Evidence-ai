"""create ask_history

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ask_history",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "owner_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "collection_id",
            sa.Uuid(),
            sa.ForeignKey("collections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("sufficient_evidence", sa.Boolean(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_ask_history_owner_id", "ask_history", ["owner_id"])
    op.create_index("ix_ask_history_created_at", "ask_history", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_ask_history_created_at", table_name="ask_history")
    op.drop_index("ix_ask_history_owner_id", table_name="ask_history")
    op.drop_table("ask_history")
