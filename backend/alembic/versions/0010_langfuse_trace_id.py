"""add langfuse_trace_id columns

Revision ID: 0010_langfuse_trace_id
Revises: 0009_smartrag_agent
Create Date: 2026-05-01 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0010_langfuse_trace_id"
down_revision = "0009_smartrag_agent"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("rag_flow_runs", sa.Column("langfuse_trace_id", sa.String(200), nullable=True))
    op.add_column("smartrag_agent_runs", sa.Column("langfuse_trace_id", sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column("smartrag_agent_runs", "langfuse_trace_id")
    op.drop_column("rag_flow_runs", "langfuse_trace_id")
