"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "model_connections",
        sa.Column("model_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=True, index=True),
        sa.Column("display_name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("model_category", sa.String(length=40), nullable=False, index=True),
        sa.Column("provider", sa.String(length=60), nullable=False, index=True),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("model_name", sa.String(length=200), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("api_version", sa.String(length=80), nullable=True),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("connection_status", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("resolved_model_name", sa.String(length=200), nullable=True),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("max_output_tokens", sa.Integer(), nullable=True),
        sa.Column("embedding_dimension", sa.Integer(), nullable=True),
        sa.Column("supports_streaming", sa.Boolean(), nullable=True),
        sa.Column("supports_json_schema", sa.Boolean(), nullable=True),
        sa.Column("supports_tools", sa.Boolean(), nullable=True),
        sa.Column("supports_vision", sa.Boolean(), nullable=True),
        sa.Column("supports_batch", sa.Boolean(), nullable=True),
        sa.Column("model_traits", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("pricing", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "model_health_checks",
        sa.Column("check_id", sa.String(length=36), primary_key=True),
        sa.Column("model_id", sa.String(length=36), sa.ForeignKey("model_connections.model_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("response_metadata", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "agent_profiles",
        sa.Column("agent_id", sa.String(length=36), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=True, index=True),
        sa.Column("agent_name", sa.String(length=120), nullable=False, unique=True),
        sa.Column("agent_type", sa.String(length=60), nullable=False, index=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "agent_profile_versions",
        sa.Column("version_id", sa.String(length=36), primary_key=True),
        sa.Column("agent_id", sa.String(length=36), sa.ForeignKey("agent_profiles.agent_id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("agent_type", sa.String(length=60), nullable=False),
        sa.Column("model_id", sa.String(length=36), sa.ForeignKey("model_connections.model_id", ondelete="RESTRICT"), nullable=False, index=True),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("runtime_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("dry_run_status", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("dry_run_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_profile_version"),
    )
    op.create_table(
        "model_defaults",
        sa.Column("default_key", sa.String(length=80), primary_key=True),
        sa.Column("model_id", sa.String(length=36), sa.ForeignKey("model_connections.model_id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "model_usage_events",
        sa.Column("event_id", sa.String(length=36), primary_key=True),
        sa.Column("model_id", sa.String(length=36), sa.ForeignKey("model_connections.model_id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_usage", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("model_usage_events")
    op.drop_table("model_defaults")
    op.drop_table("agent_profile_versions")
    op.drop_table("agent_profiles")
    op.drop_table("model_health_checks")
    op.drop_table("model_connections")

