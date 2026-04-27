from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return str(uuid.uuid4())


class ModelConnection(Base):
    __tablename__ = "model_connections"

    model_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    display_name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    model_category: Mapped[str] = mapped_column(String(40), index=True)
    provider: Mapped[str] = mapped_column(String(60), index=True)
    base_url: Mapped[str] = mapped_column(String(500))
    model_name: Mapped[str] = mapped_column(String(200))
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    api_version: Mapped[str | None] = mapped_column(String(80))
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_retries: Mapped[int] = mapped_column(Integer, default=2)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    connection_status: Mapped[str] = mapped_column(String(30), default="unknown")
    last_check_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    resolved_model_name: Mapped[str | None] = mapped_column(String(200))
    context_window: Mapped[int | None] = mapped_column(Integer)
    max_output_tokens: Mapped[int | None] = mapped_column(Integer)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer)
    supports_streaming: Mapped[bool | None] = mapped_column(Boolean)
    supports_json_schema: Mapped[bool | None] = mapped_column(Boolean)
    supports_tools: Mapped[bool | None] = mapped_column(Boolean)
    supports_vision: Mapped[bool | None] = mapped_column(Boolean)
    supports_batch: Mapped[bool | None] = mapped_column(Boolean)
    model_traits: Mapped[list[str]] = mapped_column(JSON, default=list)
    pricing: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    health_checks: Mapped[list[ModelHealthCheck]] = relationship(back_populates="model", cascade="all, delete-orphan")


class ModelHealthCheck(Base):
    __tablename__ = "model_health_checks"

    check_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    model_id: Mapped[str] = mapped_column(ForeignKey("model_connections.model_id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(30))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    response_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    model: Mapped[ModelConnection] = relationship(back_populates="health_checks")


class AgentProfile(Base):
    __tablename__ = "agent_profiles"

    agent_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    agent_name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    agent_type: Mapped[str] = mapped_column(String(60), index=True)
    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_connections.model_id", ondelete="RESTRICT"), index=True
    )
    prompt_template: Mapped[str] = mapped_column(Text)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    runtime_config: Mapped[dict] = mapped_column(JSON, default=dict)
    dry_run_status: Mapped[str] = mapped_column(String(30), default="unknown")
    dry_run_error: Mapped[str | None] = mapped_column(Text)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    model: Mapped[ModelConnection] = relationship()


class ModelDefault(Base):
    __tablename__ = "model_defaults"

    default_key: Mapped[str] = mapped_column(String(80), primary_key=True)
    model_id: Mapped[str | None] = mapped_column(ForeignKey("model_connections.model_id", ondelete="SET NULL"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ModelUsageEvent(Base):
    __tablename__ = "model_usage_events"

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    model_id: Mapped[str | None] = mapped_column(ForeignKey("model_connections.model_id", ondelete="SET NULL"), index=True)
    event_type: Mapped[str] = mapped_column(String(60))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class MaterialBatch(Base):
    __tablename__ = "material_batches"

    batch_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    batch_name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    current_version_id: Mapped[str | None] = mapped_column(String(36))
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    files: Mapped[list["MaterialFile"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan"
    )
    versions: Mapped[list["MaterialBatchVersion"]] = relationship(
        back_populates="batch", cascade="all, delete-orphan", order_by="MaterialBatchVersion.version_number"
    )


class MaterialFile(Base):
    __tablename__ = "material_files"

    file_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("material_batches.batch_id", ondelete="CASCADE"), index=True
    )
    original_filename: Mapped[str] = mapped_column(String(300))
    file_ext: Mapped[str] = mapped_column(String(40), index=True)
    mime_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer)
    checksum: Mapped[str] = mapped_column(String(64), index=True)
    storage_uri: Mapped[str] = mapped_column(String(800))
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    batch: Mapped[MaterialBatch] = relationship(back_populates="files")


class MaterialBatchVersion(Base):
    __tablename__ = "material_batch_versions"

    batch_version_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("material_batches.batch_id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    parent_version_id: Mapped[str | None] = mapped_column(String(36))
    change_type: Mapped[str] = mapped_column(String(40))
    added_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    removed_file_ids: Mapped[list[str]] = mapped_column(JSON, default=list)
    active_file_ids_snapshot: Mapped[list[str]] = mapped_column(JSON, default=list)
    manifest_uri: Mapped[str | None] = mapped_column(String(800))
    created_by: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    batch: Mapped[MaterialBatch] = relationship(back_populates="versions")


class ProcessingDefaultRule(Base):
    __tablename__ = "processing_default_rules"

    rule_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str | None] = mapped_column(String(64), index=True)
    file_ext: Mapped[str] = mapped_column(String(40), index=True)
    parser_name: Mapped[str] = mapped_column(String(120))
    parser_config_yaml: Mapped[str | None] = mapped_column(Text)
    chunker_plugin_id: Mapped[str | None] = mapped_column(String(160))
    metadata_strategy_id: Mapped[str | None] = mapped_column(String(160))
    embedding_text_template_id: Mapped[str | None] = mapped_column(String(160))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ParserStrategy(Base):
    __tablename__ = "parser_strategies"

    parser_name: Mapped[str] = mapped_column(String(120), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    supported_file_exts: Mapped[list[str]] = mapped_column(JSON, default=list)
    capabilities: Mapped[list[str]] = mapped_column(JSON, default=list)
    config_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    source: Mapped[str] = mapped_column(String(80), default="built_in")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    loaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ParseRun(Base):
    __tablename__ = "parse_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    batch_id: Mapped[str] = mapped_column(
        ForeignKey("material_batches.batch_id", ondelete="CASCADE"), index=True
    )
    batch_version_id: Mapped[str | None] = mapped_column(String(36), index=True)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    completed_files: Mapped[int] = mapped_column(Integer, default=0)
    failed_files: Mapped[int] = mapped_column(Integer, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    batch: Mapped[MaterialBatch] = relationship()
    file_runs: Mapped[list["ParseFileRun"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="ParseFileRun.created_at"
    )


class ParseFileRun(Base):
    __tablename__ = "parse_file_runs"

    file_run_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("parse_runs.run_id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(
        ForeignKey("material_files.file_id", ondelete="CASCADE"), index=True
    )
    parser_name: Mapped[str] = mapped_column(String(120), index=True)
    parser_config: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    quality_score: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)
    output_artifact_uri: Mapped[str | None] = mapped_column(String(800))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    run: Mapped[ParseRun] = relationship(back_populates="file_runs")
    file: Mapped[MaterialFile] = relationship()
    parsed_document: Mapped["ParsedDocument | None"] = relationship(
        back_populates="file_run", cascade="all, delete-orphan", uselist=False
    )


class ParsedDocument(Base):
    __tablename__ = "parsed_documents"

    parsed_document_id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("parse_runs.run_id", ondelete="CASCADE"), index=True)
    file_run_id: Mapped[str] = mapped_column(
        ForeignKey("parse_file_runs.file_run_id", ondelete="CASCADE"), index=True, unique=True
    )
    file_id: Mapped[str] = mapped_column(
        ForeignKey("material_files.file_id", ondelete="CASCADE"), index=True
    )
    parser_name: Mapped[str] = mapped_column(String(120), index=True)
    text_content: Mapped[str] = mapped_column(Text)
    elements: Mapped[list[dict]] = mapped_column(JSON, default=list)
    document_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    pages: Mapped[int] = mapped_column(Integer, default=-1)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    artifact_uri: Mapped[str | None] = mapped_column(String(800))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    file_run: Mapped[ParseFileRun] = relationship(back_populates="parsed_document")
