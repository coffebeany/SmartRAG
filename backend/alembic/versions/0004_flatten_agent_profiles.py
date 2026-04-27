"""flatten agent profiles

Revision ID: 0004_flatten_agent_profiles
Revises: 0003_parse_runs
Create Date: 2026-04-27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "0004_flatten_agent_profiles"
down_revision = "0003_parse_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_profiles", sa.Column("model_id", sa.String(length=36), nullable=True))
    op.add_column("agent_profiles", sa.Column("prompt_template", sa.Text(), nullable=True))
    op.add_column(
        "agent_profiles",
        sa.Column("output_schema", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "agent_profiles",
        sa.Column("runtime_config", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "agent_profiles",
        sa.Column("dry_run_status", sa.String(length=30), nullable=False, server_default="unknown"),
    )
    op.add_column("agent_profiles", sa.Column("dry_run_error", sa.Text(), nullable=True))
    op.create_index("ix_agent_profiles_model_id", "agent_profiles", ["model_id"])
    op.create_foreign_key(
        "fk_agent_profiles_model_id_model_connections",
        "agent_profiles",
        "model_connections",
        ["model_id"],
        ["model_id"],
        ondelete="RESTRICT",
    )

    op.execute(
        """
        UPDATE agent_profiles AS a
        SET
          model_id = v.model_id,
          prompt_template = v.prompt_template,
          output_schema = v.output_schema,
          runtime_config = v.runtime_config,
          dry_run_status = v.dry_run_status,
          dry_run_error = v.dry_run_error
        FROM agent_profile_versions AS v
        WHERE v.agent_id = a.agent_id
          AND v.version = a.current_version
        """
    )

    op.drop_table("agent_profile_versions")
    op.drop_column("agent_profiles", "current_version")


def downgrade() -> None:
    op.add_column(
        "agent_profiles",
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "agent_profile_versions",
        sa.Column("version_id", sa.String(length=36), primary_key=True),
        sa.Column(
            "agent_id",
            sa.String(length=36),
            sa.ForeignKey("agent_profiles.agent_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("agent_name", sa.String(length=120), nullable=False),
        sa.Column("agent_type", sa.String(length=60), nullable=False),
        sa.Column(
            "model_id",
            sa.String(length=36),
            sa.ForeignKey("model_connections.model_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("prompt_template", sa.Text(), nullable=False),
        sa.Column("output_schema", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("runtime_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("dry_run_status", sa.String(length=30), nullable=False, server_default="unknown"),
        sa.Column("dry_run_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_agent_profile_versions_agent_id", "agent_profile_versions", ["agent_id"]
    )
    op.create_index(
        "ix_agent_profile_versions_model_id", "agent_profile_versions", ["model_id"]
    )
    op.create_unique_constraint(
        "uq_agent_profile_version", "agent_profile_versions", ["agent_id", "version"]
    )
    op.execute(
        """
        INSERT INTO agent_profile_versions (
          version_id,
          agent_id,
          version,
          agent_name,
          agent_type,
          model_id,
          prompt_template,
          output_schema,
          runtime_config,
          dry_run_status,
          dry_run_error,
          created_at
        )
        SELECT
          gen_random_uuid()::text,
          agent_id,
          1,
          agent_name,
          agent_type,
          model_id,
          prompt_template,
          output_schema,
          runtime_config,
          dry_run_status,
          dry_run_error,
          created_at
        FROM agent_profiles
        WHERE model_id IS NOT NULL
          AND prompt_template IS NOT NULL
        """
    )
    op.drop_constraint(
        "fk_agent_profiles_model_id_model_connections", "agent_profiles", type_="foreignkey"
    )
    op.drop_index("ix_agent_profiles_model_id", table_name="agent_profiles")
    op.drop_column("agent_profiles", "dry_run_error")
    op.drop_column("agent_profiles", "dry_run_status")
    op.drop_column("agent_profiles", "runtime_config")
    op.drop_column("agent_profiles", "output_schema")
    op.drop_column("agent_profiles", "prompt_template")
    op.drop_column("agent_profiles", "model_id")
