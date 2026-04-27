from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MaterialBatchCreate(BaseModel):
    project_id: str | None = None
    batch_name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    created_by: str | None = None


class MaterialBatchUpdate(BaseModel):
    batch_name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None


class MaterialBatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_id: str
    project_id: str | None = None
    batch_name: str
    description: str | None = None
    current_version_id: str | None = None
    current_version: int
    file_count: int
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class MaterialFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_id: str
    batch_id: str
    original_filename: str
    file_ext: str
    mime_type: str | None = None
    size_bytes: int
    checksum: str
    storage_uri: str
    status: Literal["active", "removed"]
    created_at: datetime
    removed_at: datetime | None = None


class MaterialBatchVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    batch_version_id: str
    batch_id: str
    version_number: int
    parent_version_id: str | None = None
    change_type: str
    added_file_ids: list[str]
    removed_file_ids: list[str]
    active_file_ids_snapshot: list[str]
    manifest_uri: str | None = None
    created_by: str | None = None
    created_at: datetime


class UploadFilesOut(BaseModel):
    batch: MaterialBatchOut
    files: list[MaterialFileOut]
    version: MaterialBatchVersionOut
    duplicate_checksums: list[str] = Field(default_factory=list)


class ProcessingDefaultRuleUpsert(BaseModel):
    rule_id: str | None = None
    project_id: str | None = None
    file_ext: str = Field(min_length=1, max_length=40)
    parser_name: str = Field(min_length=1, max_length=120)
    parser_config_yaml: str | None = None
    chunker_plugin_id: str | None = None
    metadata_strategy_id: str | None = None
    enabled: bool = True


class ProcessingDefaultRulesUpdate(BaseModel):
    rules: list[ProcessingDefaultRuleUpsert]


class ProcessingDefaultRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    rule_id: str
    project_id: str | None = None
    file_ext: str
    parser_name: str
    parser_config_yaml: str | None = None
    chunker_plugin_id: str | None = None
    metadata_strategy_id: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ParserStrategyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parser_name: str
    display_name: str
    description: str
    supported_file_exts: list[str]
    capabilities: list[str]
    config_schema: dict
    default_config: dict = Field(default_factory=dict)
    source: str
    enabled: bool
    loaded_at: datetime
    availability_status: str
    availability_reason: str
    required_dependencies: list[str]
    required_env_vars: list[str]
    requires_config: bool
    autorag_module_type: str | None = None
    autorag_parse_method: str | None = None


class ParsePlanFileOut(BaseModel):
    file: MaterialFileOut
    default_parser_name: str | None = None
    default_parser_config: dict = Field(default_factory=dict)
    parser_options: list[ParserStrategyOut]


class ParsePlanOut(BaseModel):
    batch: MaterialBatchOut
    files: list[ParsePlanFileOut]


class ParseFileSelection(BaseModel):
    file_id: str
    parser_name: str
    parser_config: dict = Field(default_factory=dict)


class ParseRunCreate(BaseModel):
    batch_id: str
    files: list[ParseFileSelection]


class ParseRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    batch_id: str
    batch_version_id: str | None = None
    status: str
    total_files: int
    completed_files: int
    failed_files: int
    error_summary: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    batch_name: str | None = None


class ParseFileRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    file_run_id: str
    run_id: str
    file_id: str
    parser_name: str
    parser_config: dict
    status: str
    latency_ms: int | None = None
    quality_score: int | None = None
    error: str | None = None
    output_artifact_uri: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    original_filename: str | None = None
    file_ext: str | None = None


class ParsedDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    parsed_document_id: str
    run_id: str
    file_run_id: str
    file_id: str
    parser_name: str
    text_content: str
    elements: list[dict]
    document_metadata: dict
    pages: int
    char_count: int
    artifact_uri: str | None = None
    created_at: datetime


class ParseFileRunDetailOut(BaseModel):
    file_run: ParseFileRunOut
    parsed_document: ParsedDocumentOut | None = None


class ParseElementsPageOut(BaseModel):
    items: list[dict]
    total: int
    offset: int
    limit: int
