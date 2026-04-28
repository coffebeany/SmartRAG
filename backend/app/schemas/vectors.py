from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.chunks import ChunkRunOut
from app.schemas.materials import MaterialBatchOut

FileSelectionMode = Literal["all", "selected", "test_related"]


class VectorDBOut(BaseModel):
    vectordb_name: str
    display_name: str
    description: str
    db_type: str
    capabilities: list[str]
    config_schema: dict
    default_config: dict
    advanced_options_schema: dict
    default_storage_uri: str | None = None
    source: str
    enabled: bool
    availability_status: str
    availability_reason: str
    required_dependencies: list[str]


class VectorPlanFileOut(BaseModel):
    chunk_file_run_id: str
    source_file_id: str
    original_filename: str | None = None
    status: str
    chunk_count: int
    char_count: int
    token_count: int


class VectorPlanOut(BaseModel):
    batch: MaterialBatchOut
    chunk_run: ChunkRunOut
    files: list[VectorPlanFileOut]
    vectordbs: list[VectorDBOut]


class VectorFileSelection(BaseModel):
    mode: FileSelectionMode = "all"
    selected_file_ids: list[str] = Field(default_factory=list)


class VectorRunCreate(BaseModel):
    batch_id: str
    chunk_run_id: str
    embedding_model_id: str
    vectordb_name: str
    vectordb_config: dict = Field(default_factory=dict)
    embedding_config: dict = Field(default_factory=dict)
    index_config: dict = Field(default_factory=dict)
    file_selection: VectorFileSelection = Field(default_factory=VectorFileSelection)


class VectorRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    batch_id: str
    batch_version_id: str | None = None
    chunk_run_id: str
    embedding_model_id: str
    embedding_model_snapshot: dict
    vectordb_name: str
    vectordb_config: dict
    embedding_config: dict
    index_config: dict
    file_selection: dict
    collection_name: str
    storage_uri: str
    similarity_metric: str
    embedding_dimension: int | None = None
    status: str
    total_files: int
    completed_files: int
    failed_files: int
    total_chunks: int
    total_vectors: int
    stats: dict
    error_summary: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    batch_name: str | None = None
    chunk_status: str | None = None


class VectorFileRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_run_id: str
    run_id: str
    chunk_file_run_id: str
    source_file_id: str
    status: str
    chunk_count: int
    vector_count: int
    failed_vectors: int
    latency_ms: int | None = None
    error: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    original_filename: str | None = None


class VectorRunCompareOut(BaseModel):
    run_id: str
    batch_id: str
    batch_name: str | None = None
    chunk_run_id: str
    embedding_model_id: str
    embedding_model_name: str | None = None
    vectordb_name: str
    status: str
    total_files: int
    completed_files: int
    failed_files: int
    total_chunks: int
    total_vectors: int
    similarity_metric: str
    embedding_dimension: int | None = None
    stats: dict
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
