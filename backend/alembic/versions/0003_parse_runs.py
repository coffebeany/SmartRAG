"""parse runs

Revision ID: 0003_parse_runs
Revises: 0002_material_management
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0003_parse_runs"
down_revision = "0002_material_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parse_runs",
        sa.Column("run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("material_batches.batch_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("batch_version_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("total_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_files", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_parse_runs_batch_id", "parse_runs", ["batch_id"])
    op.create_index("ix_parse_runs_batch_version_id", "parse_runs", ["batch_version_id"])
    op.create_index("ix_parse_runs_status", "parse_runs", ["status"])

    op.create_table(
        "parse_file_runs",
        sa.Column("file_run_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("parse_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_id",
            sa.String(length=36),
            sa.ForeignKey("material_files.file_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parser_name", sa.String(length=120), nullable=False),
        sa.Column("parser_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("output_artifact_uri", sa.String(length=800), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_parse_file_runs_run_id", "parse_file_runs", ["run_id"])
    op.create_index("ix_parse_file_runs_file_id", "parse_file_runs", ["file_id"])
    op.create_index("ix_parse_file_runs_parser_name", "parse_file_runs", ["parser_name"])
    op.create_index("ix_parse_file_runs_status", "parse_file_runs", ["status"])

    op.create_table(
        "parsed_documents",
        sa.Column("parsed_document_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=36),
            sa.ForeignKey("parse_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "file_run_id",
            sa.String(length=36),
            sa.ForeignKey("parse_file_runs.file_run_id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "file_id",
            sa.String(length=36),
            sa.ForeignKey("material_files.file_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("parser_name", sa.String(length=120), nullable=False),
        sa.Column("text_content", sa.Text(), nullable=False),
        sa.Column("elements", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("document_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("pages", sa.Integer(), nullable=False, server_default="-1"),
        sa.Column("char_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("artifact_uri", sa.String(length=800), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_parsed_documents_run_id", "parsed_documents", ["run_id"])
    op.create_index("ix_parsed_documents_file_run_id", "parsed_documents", ["file_run_id"])
    op.create_index("ix_parsed_documents_file_id", "parsed_documents", ["file_id"])
    op.create_index("ix_parsed_documents_parser_name", "parsed_documents", ["parser_name"])


def downgrade() -> None:
    op.drop_index("ix_parsed_documents_parser_name", table_name="parsed_documents")
    op.drop_index("ix_parsed_documents_file_id", table_name="parsed_documents")
    op.drop_index("ix_parsed_documents_file_run_id", table_name="parsed_documents")
    op.drop_index("ix_parsed_documents_run_id", table_name="parsed_documents")
    op.drop_table("parsed_documents")
    op.drop_index("ix_parse_file_runs_status", table_name="parse_file_runs")
    op.drop_index("ix_parse_file_runs_parser_name", table_name="parse_file_runs")
    op.drop_index("ix_parse_file_runs_file_id", table_name="parse_file_runs")
    op.drop_index("ix_parse_file_runs_run_id", table_name="parse_file_runs")
    op.drop_table("parse_file_runs")
    op.drop_index("ix_parse_runs_status", table_name="parse_runs")
    op.drop_index("ix_parse_runs_batch_version_id", table_name="parse_runs")
    op.drop_index("ix_parse_runs_batch_id", table_name="parse_runs")
    op.drop_table("parse_runs")
