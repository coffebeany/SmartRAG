"""smartrag agent

Revision ID: 0009_smartrag_agent
Revises: 0008_evaluation_framework
Create Date: 2026-04-28 00:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0009_smartrag_agent"
down_revision = "0008_evaluation_framework"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "smartrag_agent_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("model_id", sa.String(length=36), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("enabled_action_names", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("answer", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["model_id"], ["model_connections.model_id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index(op.f("ix_smartrag_agent_runs_model_id"), "smartrag_agent_runs", ["model_id"], unique=False)
    op.create_index(op.f("ix_smartrag_agent_runs_status"), "smartrag_agent_runs", ["status"], unique=False)

    op.create_table(
        "smartrag_agent_run_events",
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["smartrag_agent_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(op.f("ix_smartrag_agent_run_events_event_type"), "smartrag_agent_run_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_smartrag_agent_run_events_run_id"), "smartrag_agent_run_events", ["run_id"], unique=False)
    op.create_index(op.f("ix_smartrag_agent_run_events_sequence"), "smartrag_agent_run_events", ["sequence"], unique=False)

    op.create_table(
        "smartrag_agent_tool_logs",
        sa.Column("tool_log_id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("tool_name", sa.String(length=160), nullable=False),
        sa.Column("tool_args", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("output", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["smartrag_agent_runs.run_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tool_log_id"),
    )
    op.create_index(op.f("ix_smartrag_agent_tool_logs_run_id"), "smartrag_agent_tool_logs", ["run_id"], unique=False)
    op.create_index(op.f("ix_smartrag_agent_tool_logs_status"), "smartrag_agent_tool_logs", ["status"], unique=False)
    op.create_index(op.f("ix_smartrag_agent_tool_logs_tool_name"), "smartrag_agent_tool_logs", ["tool_name"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_smartrag_agent_tool_logs_tool_name"), table_name="smartrag_agent_tool_logs")
    op.drop_index(op.f("ix_smartrag_agent_tool_logs_status"), table_name="smartrag_agent_tool_logs")
    op.drop_index(op.f("ix_smartrag_agent_tool_logs_run_id"), table_name="smartrag_agent_tool_logs")
    op.drop_table("smartrag_agent_tool_logs")
    op.drop_index(op.f("ix_smartrag_agent_run_events_sequence"), table_name="smartrag_agent_run_events")
    op.drop_index(op.f("ix_smartrag_agent_run_events_run_id"), table_name="smartrag_agent_run_events")
    op.drop_index(op.f("ix_smartrag_agent_run_events_event_type"), table_name="smartrag_agent_run_events")
    op.drop_table("smartrag_agent_run_events")
    op.drop_index(op.f("ix_smartrag_agent_runs_status"), table_name="smartrag_agent_runs")
    op.drop_index(op.f("ix_smartrag_agent_runs_model_id"), table_name="smartrag_agent_runs")
    op.drop_table("smartrag_agent_runs")
