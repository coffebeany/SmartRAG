from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ParseEvaluatorOut(BaseModel):
    evaluator_name: str
    display_name: str
    description: str
    capabilities: list[str]
    config_schema: dict
    default_config: dict = Field(default_factory=dict)
    source: str
    enabled: bool
    availability_status: str
    availability_reason: str


class ParseEvaluationRunCreate(BaseModel):
    batch_id: str
    parse_run_id: str | None = None
    evaluator_name: str
    evaluator_config: dict = Field(default_factory=dict)


class EvaluationMetricOut(BaseModel):
    metric_id: str
    display_name: str
    description: str
    category: str
    requires_answer: bool = True
    requires_ground_truth: bool = True
    requires_contexts: bool = True


class EvaluationFrameworkOut(BaseModel):
    framework_id: str
    display_name: str
    description: str
    source: str
    default_metrics: list[str]
    metrics: list[EvaluationMetricOut]
    generator_config_schema: dict = Field(default_factory=dict)
    default_generator_config: dict = Field(default_factory=dict)
    availability_status: str
    availability_reason: str
    dependency_install_hint: str | None = None


class EvaluationDatasetRunCreate(BaseModel):
    batch_id: str
    chunk_run_id: str
    framework_id: str = "ragas"
    generator_config: dict = Field(default_factory=dict)
    judge_llm_model_id: str | None = None
    embedding_model_id: str | None = None


class EvaluationDatasetRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    batch_id: str
    chunk_run_id: str
    framework_id: str
    generator_config: dict
    judge_llm_model_id: str | None = None
    embedding_model_id: str | None = None
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    stats: dict
    error_summary: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    batch_name: str | None = None
    chunk_status: str | None = None


class EvaluationDatasetItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    run_id: str
    question: str
    ground_truth: str
    reference_contexts: list[str]
    source_chunk_ids: list[str]
    source_file_ids: list[str]
    synthesizer_name: str | None = None
    item_metadata: dict
    created_at: datetime


class EvaluationDatasetItemsPageOut(BaseModel):
    items: list[EvaluationDatasetItemOut]
    total: int
    offset: int
    limit: int


class EvaluationReportRunCreate(BaseModel):
    flow_id: str
    dataset_run_id: str
    framework_id: str = "ragas"
    metric_ids: list[str] = Field(default_factory=list)
    evaluator_config: dict = Field(default_factory=dict)


class EvaluationReportRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    flow_id: str
    dataset_run_id: str
    framework_id: str
    metric_ids: list[str]
    evaluator_config: dict
    aggregate_scores: dict
    status: str
    total_items: int
    completed_items: int
    failed_items: int
    error_summary: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    flow_name: str | None = None
    dataset_status: str | None = None


class EvaluationReportItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    item_id: str
    run_id: str
    dataset_item_id: str
    rag_flow_run_id: str | None = None
    question: str
    answer: str | None = None
    contexts: list[str]
    retrieved_chunk_ids: list[str]
    scores: dict
    trace_events: list[dict]
    latency_ms: int | None = None
    error: str | None = None
    created_at: datetime


class EvaluationReportItemsPageOut(BaseModel):
    items: list[EvaluationReportItemOut]
    total: int
    offset: int
    limit: int
