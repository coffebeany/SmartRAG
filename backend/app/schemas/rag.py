from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RagComponentOut(BaseModel):
    node_type: str
    module_type: str
    display_name: str
    description: str
    capabilities: list[str]
    config_schema: dict
    secret_config_schema: dict
    default_config: dict
    source: str
    executable: bool
    requires_config: bool
    required_dependencies: list[str]
    required_env_vars: list[str]
    requires_llm: bool
    requires_embedding: bool
    requires_api_key: bool
    dependency_install_hint: str | None = None
    availability_status: str
    availability_reason: str


class ComponentConfigCreate(BaseModel):
    node_type: str
    module_type: str
    display_name: str = Field(min_length=1, max_length=160)
    config: dict = Field(default_factory=dict)
    secret_config: dict = Field(default_factory=dict)
    enabled: bool = True


class ComponentConfigUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=160)
    config: dict | None = None
    secret_config: dict | None = None
    enabled: bool | None = None


class ComponentConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    config_id: str
    node_type: str
    module_type: str
    display_name: str
    config: dict
    secret_config_masked: dict = Field(default_factory=dict)
    enabled: bool
    availability_status: str = "unknown"
    availability_reason: str = ""
    created_at: datetime
    updated_at: datetime


class RagFlowNode(BaseModel):
    node_type: str
    module_type: str
    config: dict = Field(default_factory=dict)
    component_config_id: str | None = None
    enabled: bool = True


class RagFlowCreate(BaseModel):
    flow_name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    vector_run_id: str
    retrieval_config: dict = Field(default_factory=lambda: {"top_k": 5})
    nodes: list[RagFlowNode] = Field(default_factory=list)
    enabled: bool = True


class RagFlowUpdate(BaseModel):
    flow_name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    vector_run_id: str | None = None
    retrieval_config: dict | None = None
    nodes: list[RagFlowNode] | None = None
    enabled: bool | None = None


class RagFlowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    flow_id: str
    flow_name: str
    description: str | None = None
    vector_run_id: str
    vector_run_status: str | None = None
    batch_name: str | None = None
    vectordb_name: str | None = None
    retrieval_config: dict
    nodes: list[dict]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class RagFlowRunCreate(BaseModel):
    query: str = Field(min_length=1)


class RagPassageOut(BaseModel):
    chunk_id: str
    contents: str
    score: float
    source_file_id: str | None = None
    original_filename: str | None = None
    chunk_index: int | None = None
    metadata: dict = Field(default_factory=dict)


class RagTraceEventOut(BaseModel):
    node_type: str
    module_type: str
    status: str
    activated: bool
    input_summary: dict = Field(default_factory=dict)
    output_summary: dict = Field(default_factory=dict)
    latency_ms: int | None = None
    error: str | None = None


class RagFlowRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    flow_id: str
    query: str
    status: str
    answer: str | None = None
    answer_metadata: dict = Field(default_factory=dict)
    final_passages: list[dict]
    trace_events: list[dict]
    latency_ms: int | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
