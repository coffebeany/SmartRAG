"""Add RAG component configs and flows.

Revision ID: 0007_rag_flows
Revises: 0006_vector_runs
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_rag_flows"
down_revision: str | None = "0006_vector_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "component_configs",
        sa.Column("config_id", sa.String(length=36), nullable=False),
        sa.Column("node_type", sa.String(length=80), nullable=False, index=True),
        sa.Column("module_type", sa.String(length=120), nullable=False, index=True),
        sa.Column("display_name", sa.String(length=160), nullable=False, index=True),
        sa.Column("config", sa.JSON(), nullable=False),
        sa.Column("secret_config_encrypted", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("config_id"),
    )
    op.create_table(
        "rag_flows",
        sa.Column("flow_id", sa.String(length=36), nullable=False),
        sa.Column("flow_name", sa.String(length=160), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "vector_run_id",
            sa.String(length=36),
            sa.ForeignKey("vector_runs.run_id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("retrieval_config", sa.JSON(), nullable=False),
        sa.Column("nodes", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true(), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("flow_id"),
    )
    op.create_table(
        "rag_flow_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "flow_id",
            sa.String(length=36),
            sa.ForeignKey("rag_flows.flow_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending", index=True),
        sa.Column("final_passages", sa.JSON(), nullable=False),
        sa.Column("trace_events", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )


def downgrade() -> None:
    op.drop_table("rag_flow_runs")
    op.drop_table("rag_flows")
    op.drop_table("component_configs")
