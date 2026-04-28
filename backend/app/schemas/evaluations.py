from __future__ import annotations

from pydantic import BaseModel, Field


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
