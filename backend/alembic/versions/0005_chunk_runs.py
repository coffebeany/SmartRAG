"""chunk runs

Revision ID: 0005_chunk_runs
Revises: 0004_flatten_agent_profiles
Create Date: 2026-04-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0005_chunk_runs"
down_revision = "0004_flatten_agent_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "chunk_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("material_batches.batch_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("batch_version_id", sa.String(length=36), nullable=True),
        sa.Column(
            "parse_run_id",
            sa.String(length=36),
            sa.ForeignKey("parse_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunker_name", sa.String(length=120), nullable=False),
        sa.Column("chunker_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_chunks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stats", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("artifact_uri", sa.String(length=800), nullable=True),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chunk_runs_batch_id", "chunk_runs", ["batch_id"])
    op.create_index("ix_chunk_runs_batch_version_id", "chunk_runs", ["batch_version_id"])
    op.create_index("ix_chunk_runs_parse_run_id", "chunk_runs", ["parse_run_id"])
    op.create_index("ix_chunk_runs_chunker_name", "chunk_runs", ["chunker_name"])
    op.create_index("ix_chunk_runs_status", "chunk_runs", ["status"])

    op.create_table(
        "chunk_file_runs",
        sa.Column("file_run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("chunk_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parsed_document_id",
            sa.String(length=36),
            sa.ForeignKey("parsed_documents.parsed_document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            sa.String(length=36),
            sa.ForeignKey("material_files.file_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("artifact_uri", sa.String(length=800), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chunk_file_runs_run_id", "chunk_file_runs", ["run_id"])
    op.create_index("ix_chunk_file_runs_parsed_document_id", "chunk_file_runs", ["parsed_document_id"])
    op.create_index("ix_chunk_file_runs_source_file_id", "chunk_file_runs", ["source_file_id"])
    op.create_index("ix_chunk_file_runs_status", "chunk_file_runs", ["status"])

    op.create_table(
        "chunks",
        sa.Column("chunk_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("chunk_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_run_id",
            sa.String(length=36),
            sa.ForeignKey("chunk_file_runs.file_run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parsed_document_id",
            sa.String(length=36),
            sa.ForeignKey("parsed_documents.parsed_document_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_file_id",
            sa.String(length=36),
            sa.ForeignKey("material_files.file_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("contents", sa.Text(), nullable=False),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("start_char", sa.Integer(), nullable=False),
        sa.Column("end_char", sa.Integer(), nullable=False),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("source_element_refs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("strategy_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_chunks_run_id", "chunks", ["run_id"])
    op.create_index("ix_chunks_file_run_id", "chunks", ["file_run_id"])
    op.create_index("ix_chunks_parsed_document_id", "chunks", ["parsed_document_id"])
    op.create_index("ix_chunks_source_file_id", "chunks", ["source_file_id"])
    op.create_index("ix_chunks_chunk_index", "chunks", ["chunk_index"])


def downgrade() -> None:
    op.drop_index("ix_chunks_chunk_index", table_name="chunks")
    op.drop_index("ix_chunks_source_file_id", table_name="chunks")
    op.drop_index("ix_chunks_parsed_document_id", table_name="chunks")
    op.drop_index("ix_chunks_file_run_id", table_name="chunks")
    op.drop_index("ix_chunks_run_id", table_name="chunks")
    op.drop_table("chunks")
    op.drop_index("ix_chunk_file_runs_status", table_name="chunk_file_runs")
    op.drop_index("ix_chunk_file_runs_source_file_id", table_name="chunk_file_runs")
    op.drop_index("ix_chunk_file_runs_parsed_document_id", table_name="chunk_file_runs")
    op.drop_index("ix_chunk_file_runs_run_id", table_name="chunk_file_runs")
    op.drop_table("chunk_file_runs")
    op.drop_index("ix_chunk_runs_status", table_name="chunk_runs")
    op.drop_index("ix_chunk_runs_chunker_name", table_name="chunk_runs")
    op.drop_index("ix_chunk_runs_parse_run_id", table_name="chunk_runs")
    op.drop_index("ix_chunk_runs_batch_version_id", table_name="chunk_runs")
    op.drop_index("ix_chunk_runs_batch_id", table_name="chunk_runs")
    op.drop_table("chunk_runs")
