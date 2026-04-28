"""Add vectorization runs.

Revision ID: 0006_vector_runs
Revises: 0005_chunk_runs
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_vector_runs"
down_revision: str | None = "0005_chunk_runs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "vector_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("material_batches.batch_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("batch_version_id", sa.String(length=36), nullable=True, index=True),
        sa.Column(
            "chunk_run_id",
            sa.String(length=36),
            sa.ForeignKey("chunk_runs.run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "embedding_model_id",
            sa.String(length=36),
            sa.ForeignKey("model_connections.model_id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        ),
        sa.Column("embedding_model_snapshot", sa.JSON(), nullable=False),
        sa.Column("vectordb_name", sa.String(length=120), nullable=False, index=True),
        sa.Column("vectordb_config", sa.JSON(), nullable=False),
        sa.Column("embedding_config", sa.JSON(), nullable=False),
        sa.Column("index_config", sa.JSON(), nullable=False),
        sa.Column("file_selection", sa.JSON(), nullable=False),
        sa.Column("collection_name", sa.String(length=180), nullable=False, index=True),
        sa.Column("storage_uri", sa.String(length=800), nullable=False),
        sa.Column("similarity_metric", sa.String(length=40), nullable=False, server_default="cosine"),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending", index=True),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_vectors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_table(
        "vector_file_runs",
        sa.Column("file_run_id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("vector_runs.run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "chunk_file_run_id",
            sa.String(length=36),
            sa.ForeignKey("chunk_file_runs.file_run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_file_id",
            sa.String(length=36),
            sa.ForeignKey("material_files.file_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending", index=True),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("vector_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_vectors", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("file_run_id"),
    )
    op.create_table(
        "vector_items",
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("vector_runs.run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "file_run_id",
            sa.String(length=36),
            sa.ForeignKey("vector_file_runs.file_run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "chunk_id",
            sa.String(length=36),
            sa.ForeignKey("chunks.chunk_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "source_file_id",
            sa.String(length=36),
            sa.ForeignKey("material_files.file_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("vector_id", sa.String(length=220), nullable=False, index=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False, index=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=False),
        sa.Column("item_metadata", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="stored", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("item_id"),
    )
    op.create_table(
        "vector_run_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("vector_runs.run_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("event_type", sa.String(length=80), nullable=False, index=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="info", index=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("event_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("event_id"),
    )


def downgrade() -> None:
    op.drop_table("vector_run_events")
    op.drop_table("vector_items")
    op.drop_table("vector_file_runs")
    op.drop_table("vector_runs")
