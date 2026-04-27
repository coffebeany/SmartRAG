from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AgentType = Literal[
    "custom",
    "query_rewrite",
    "query_compress",
    "multi_query",
    "query_decompose",
    "hyde",
    "metadata_extraction",
    "routing",
    "failure_analysis",
    "strategy_planner",
    "llm_judge",
]


class AgentProfileCreate(BaseModel):
    project_id: str | None = None
    agent_name: str = Field(min_length=1, max_length=120)
    agent_type: AgentType
    model_id: str
    prompt_template: str = Field(min_length=1)
    runtime_config: dict = Field(default_factory=lambda: {"temperature": 0.0, "max_output_tokens": 2048})
    enabled: bool = True


class AgentProfileUpdate(BaseModel):
    agent_name: str | None = Field(default=None, min_length=1, max_length=120)
    agent_type: AgentType | None = None
    model_id: str | None = None
    prompt_template: str | None = None
    runtime_config: dict | None = None
    enabled: bool | None = None


class AgentProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    agent_id: str
    project_id: str | None = None
    agent_name: str
    agent_type: str
    model_id: str
    prompt_template: str
    output_schema: dict
    runtime_config: dict
    dry_run_status: str
    dry_run_error: str | None = None
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AgentDryRunRequest(BaseModel):
    input_text: str | None = "Hello,SmartRAG!"
    variables: dict = Field(default_factory=dict)


class AgentDraftDryRunRequest(AgentDryRunRequest):
    model_id: str
    prompt_template: str = Field(min_length=1)
    runtime_config: dict = Field(default_factory=dict)


class AgentDryRunOut(BaseModel):
    status: str
    output: str | dict | None = None
    latency_ms: int | None = None
    error: str | None = None
    trace: dict = Field(default_factory=dict)


class AgentTypeInfo(BaseModel):
    agent_type: AgentType
    display_name: str
    default_prompt: str
    output_schema: dict
