from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.materials import MaterialBatchOut, ParseRunOut


class ChunkStrategyOut(BaseModel):
    chunker_name: str
    display_name: str
    description: str
    module_type: str
    chunk_method: str
    capabilities: list[str]
    config_schema: dict
    default_config: dict = Field(default_factory=dict)
    source: str
    enabled: bool
    availability_status: str
    availability_reason: str
    required_dependencies: list[str]
    requires_embedding_model: bool


class ChunkPlanFileOut(BaseModel):
    parsed_document_id: str
    file_id: str
    original_filename: str | None = None
    parser_name: str
    char_count: int
    pages: int


class ChunkPlanOut(BaseModel):
    batch: MaterialBatchOut
    parse_run: ParseRunOut
    files: list[ChunkPlanFileOut]
    chunk_options: list[ChunkStrategyOut]


class ChunkRunCreate(BaseModel):
    batch_id: str
    parse_run_id: str
    chunker_name: str
    chunker_config: dict = Field(default_factory=dict)


class ChunkRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    batch_id: str
    batch_version_id: str | None = None
    parse_run_id: str
    chunker_name: str
    chunker_config: dict
    status: str
    total_files: int
    completed_files: int
    failed_files: int
    total_chunks: int
    stats: dict
    artifact_uri: str | None = None
    error_summary: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    batch_name: str | None = None
    parse_status: str | None = None


class ChunkFileRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_run_id: str
    run_id: str
    parsed_document_id: str
    source_file_id: str
    status: str
    chunk_count: int
    latency_ms: int | None = None
    error: str | None = None
    artifact_uri: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    original_filename: str | None = None
    parser_name: str | None = None


class ChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    chunk_id: str
    run_id: str
    file_run_id: str
    parsed_document_id: str
    source_file_id: str
    chunk_index: int
    contents: str
    source_text: str
    start_char: int
    end_char: int
    char_count: int
    token_count: int
    chunk_metadata: dict
    source_element_refs: list[dict]
    strategy_metadata: dict
    created_at: datetime


class ChunkPageOut(BaseModel):
    items: list[ChunkOut]
    total: int
    offset: int
    limit: int


class ChunkFileRunDetailOut(BaseModel):
    file_run: ChunkFileRunOut
    chunks: ChunkPageOut | None = None


class ChunkRunCompareOut(BaseModel):
    run_id: str
    batch_id: str
    batch_name: str | None = None
    parse_run_id: str
    chunker_name: str
    status: str
    total_files: int
    completed_files: int
    failed_files: int
    total_chunks: int
    stats: dict
    chunker_config: dict
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
