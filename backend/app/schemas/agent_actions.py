from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AgentRunStatus = Literal["pending", "running", "completed", "failed", "cancelled"]
AgentRunEventType = Literal[
    "message_delta",
    "reasoning_delta",
    "tool_call_started",
    "tool_call_result",
    "tool_call_error",
    "final_answer",
    "run_error",
    "run_cancelled",
]


class AgentActionSpecOut(BaseModel):
    name: str
    title: str
    description: str
    input_schema: dict
    output_schema: dict
    permission_scope: str
    is_destructive: bool
    tags: list[str] = Field(default_factory=list)
    resource_uri_template: str | None = None


class AgentActionResult(BaseModel):
    action_name: str
    ok: bool = True
    output: dict | list | str | int | float | bool | None = None
    error: str | None = None


class AgentRunCreate(BaseModel):
    model_id: str
    message: str = Field(min_length=1)
    enabled_action_names: list[str] | None = None


class AgentToolLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    tool_log_id: str
    run_id: str
    tool_name: str
    tool_args: dict
    status: str
    output: dict | list | str | int | float | bool | None = None
    error: str | None = None
    latency_ms: int | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    created_at: datetime


class AgentRunEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    run_id: str
    event_type: AgentRunEventType
    sequence: int
    payload: dict
    created_at: datetime


class AgentRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: str
    model_id: str
    message: str
    enabled_action_names: list[str]
    status: AgentRunStatus
    answer: str | None = None
    error: str | None = None
    langfuse_trace_id: str | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    tool_logs: list[AgentToolLogOut] = Field(default_factory=list)
    events: list[AgentRunEventOut] = Field(default_factory=list)
