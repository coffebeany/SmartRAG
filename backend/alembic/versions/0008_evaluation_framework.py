"""Add evaluation datasets and reports.

Revision ID: 0008_evaluation_framework
Revises: 0007_rag_flows
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_evaluation_framework"
down_revision: str | None = "0007_rag_flows"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("rag_flow_runs", sa.Column("answer", sa.Text(), nullable=True))
    op.add_column("rag_flow_runs", sa.Column("answer_metadata", sa.JSON(), nullable=False, server_default="{}"))

    op.create_table(
        "evaluation_dataset_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("material_batches.batch_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "chunk_run_id",
            sa.String(length=36),
            sa.ForeignKey("chunk_runs.run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("framework_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("generator_config", sa.JSON(), nullable=False),
        sa.Column(
            "judge_llm_model_id",
            sa.String(length=36),
            sa.ForeignKey("model_connections.model_id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column(
            "embedding_model_id",
            sa.String(length=36),
            sa.ForeignKey("model_connections.model_id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending", index=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_table(
        "evaluation_dataset_items",
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("evaluation_dataset_runs.run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("ground_truth", sa.Text(), nullable=False),
        sa.Column("reference_contexts", sa.JSON(), nullable=False),
        sa.Column("source_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("source_file_ids", sa.JSON(), nullable=False),
        sa.Column("synthesizer_name", sa.String(length=160), nullable=True),
        sa.Column("item_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("item_id"),
    )
    op.create_table(
        "evaluation_report_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "flow_id",
            sa.String(length=36),
            sa.ForeignKey("rag_flows.flow_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "dataset_run_id",
            sa.String(length=36),
            sa.ForeignKey("evaluation_dataset_runs.run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("framework_id", sa.String(length=80), nullable=False, index=True),
        sa.Column("metric_ids", sa.JSON(), nullable=False),
        sa.Column("evaluator_config", sa.JSON(), nullable=False),
        sa.Column("aggregate_scores", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending", index=True),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_table(
        "evaluation_report_items",
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("evaluation_report_runs.run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "dataset_item_id",
            sa.String(length=36),
            sa.ForeignKey("evaluation_dataset_items.item_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "rag_flow_run_id",
            sa.String(length=36),
            sa.ForeignKey("rag_flow_runs.run_id", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("contexts", sa.JSON(), nullable=False),
        sa.Column("retrieved_chunk_ids", sa.JSON(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("trace_events", sa.JSON(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("item_id"),
    )


def downgrade() -> None:
    op.drop_table("evaluation_report_items")
    op.drop_table("evaluation_report_runs")
    op.drop_table("evaluation_dataset_items")
    op.drop_table("evaluation_dataset_runs")
    op.drop_column("rag_flow_runs", "answer_metadata")
    op.drop_column("rag_flow_runs", "answer")
