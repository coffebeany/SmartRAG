"""material management

Revision ID: 0002_material_management
Revises: 0001_initial
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0002_material_management"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "material_batches",
        sa.Column("batch_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("batch_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("current_version_id", sa.String(length=36), nullable=True),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("file_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_material_batches_project_id", "material_batches", ["project_id"])
    op.create_index("ix_material_batches_batch_name", "material_batches", ["batch_name"])

    op.create_table(
        "material_files",
        sa.Column("file_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("material_batches.batch_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("original_filename", sa.String(length=300), nullable=False),
        sa.Column("file_ext", sa.String(length=40), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("storage_uri", sa.String(length=800), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_material_files_batch_id", "material_files", ["batch_id"])
    op.create_index("ix_material_files_file_ext", "material_files", ["file_ext"])
    op.create_index("ix_material_files_checksum", "material_files", ["checksum"])
    op.create_index("ix_material_files_status", "material_files", ["status"])

    op.create_table(
        "material_batch_versions",
        sa.Column("batch_version_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "batch_id",
            sa.String(length=36),
            sa.ForeignKey("material_batches.batch_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("parent_version_id", sa.String(length=36), nullable=True),
        sa.Column("change_type", sa.String(length=40), nullable=False),
        sa.Column("added_file_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("removed_file_ids", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("active_file_ids_snapshot", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("manifest_uri", sa.String(length=800), nullable=True),
        sa.Column("created_by", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_material_batch_versions_batch_id", "material_batch_versions", ["batch_id"])

    op.create_table(
        "processing_default_rules",
        sa.Column("rule_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=True),
        sa.Column("file_ext", sa.String(length=40), nullable=False),
        sa.Column("parser_name", sa.String(length=120), nullable=False),
        sa.Column("parser_config_yaml", sa.Text(), nullable=True),
        sa.Column("chunker_plugin_id", sa.String(length=160), nullable=True),
        sa.Column("metadata_strategy_id", sa.String(length=160), nullable=True),
        sa.Column("embedding_text_template_id", sa.String(length=160), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_processing_default_rules_project_id", "processing_default_rules", ["project_id"])
    op.create_index("ix_processing_default_rules_file_ext", "processing_default_rules", ["file_ext"])

    op.create_table(
        "parser_strategies",
        sa.Column("parser_name", sa.String(length=120), primary_key=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("supported_file_exts", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("capabilities", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("config_schema", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("source", sa.String(length=80), nullable=False, server_default="built_in"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("loaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    parser_table = sa.table(
        "parser_strategies",
        sa.column("parser_name", sa.String),
        sa.column("display_name", sa.String),
        sa.column("description", sa.Text),
        sa.column("supported_file_exts", sa.JSON),
        sa.column("capabilities", sa.JSON),
        sa.column("config_schema", sa.JSON),
        sa.column("source", sa.String),
        sa.column("enabled", sa.Boolean),
    )
    op.bulk_insert(
        parser_table,
        [
            {
                "parser_name": "pymupdf",
                "display_name": "PyMuPDF",
                "description": "速度快，适合文本型 PDF，能保留页码和部分 block 信息。",
                "supported_file_exts": [".pdf"],
                "capabilities": ["pdf", "fast", "page"],
                "config_schema": {"type": "object", "properties": {"extract_images": {"type": "boolean"}}},
                "source": "built_in",
                "enabled": True,
            },
            {
                "parser_name": "unstructured",
                "display_name": "Unstructured",
                "description": "适合多种文档格式的通用解析，支持 PDF、Office、HTML 等材料。",
                "supported_file_exts": [".pdf", ".docx", ".pptx", ".html", ".md"],
                "capabilities": ["layout", "office", "html"],
                "config_schema": {"type": "object", "properties": {"strategy": {"type": "string"}}},
                "source": "built_in",
                "enabled": True,
            },
            {
                "parser_name": "markdown_text",
                "display_name": "Markdown/Text Parser",
                "description": "适合 Markdown、TXT、日志等轻量文本材料，保留标题和段落结构。",
                "supported_file_exts": [".md", ".txt", ".log"],
                "capabilities": ["text", "markdown", "fast"],
                "config_schema": {"type": "object", "properties": {"encoding": {"type": "string"}}},
                "source": "built_in",
                "enabled": True,
            },
            {
                "parser_name": "excel_structured",
                "display_name": "Excel Structured Parser",
                "description": "按 sheet、表头和行列结构解析 Excel/CSV 表格型材料。",
                "supported_file_exts": [".xlsx", ".xls", ".csv"],
                "capabilities": ["table", "sheet", "structured"],
                "config_schema": {"type": "object", "properties": {"header_row": {"type": "integer"}}},
                "source": "built_in",
                "enabled": True,
            },
            {
                "parser_name": "plain_text",
                "display_name": "Plain Text Parser",
                "description": "最小文本解析器，适合无结构纯文本材料。",
                "supported_file_exts": [".txt", ".json", ".csv"],
                "capabilities": ["text", "cheap", "fast"],
                "config_schema": {"type": "object", "properties": {}},
                "source": "built_in",
                "enabled": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("parser_strategies")
    op.drop_index("ix_processing_default_rules_file_ext", table_name="processing_default_rules")
    op.drop_index("ix_processing_default_rules_project_id", table_name="processing_default_rules")
    op.drop_table("processing_default_rules")
    op.drop_index("ix_material_batch_versions_batch_id", table_name="material_batch_versions")
    op.drop_table("material_batch_versions")
    op.drop_index("ix_material_files_status", table_name="material_files")
    op.drop_index("ix_material_files_checksum", table_name="material_files")
    op.drop_index("ix_material_files_file_ext", table_name="material_files")
    op.drop_index("ix_material_files_batch_id", table_name="material_files")
    op.drop_table("material_files")
    op.drop_index("ix_material_batches_batch_name", table_name="material_batches")
    op.drop_index("ix_material_batches_project_id", table_name="material_batches")
    op.drop_table("material_batches")

