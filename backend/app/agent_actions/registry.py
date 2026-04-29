from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.agent_actions import AgentActionResult, AgentActionSpecOut


class EmptyActionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IdInput(BaseModel):
    id: str = Field(description="Resource identifier.")


@dataclass(slots=True)
class AgentActionContext:
    session: AsyncSession
    run_id: str | None = None
    actor: str | None = None


ActionHandler = Callable[[AgentActionContext, BaseModel], Awaitable[Any]]


@dataclass(slots=True)
class SmartRAGAction:
    name: str
    title: str
    description: str
    input_model: type[BaseModel] = EmptyActionInput
    output_schema: dict[str, Any] = field(default_factory=dict)
    permission_scope: str = "read"
    is_destructive: bool = False
    tags: list[str] = field(default_factory=list)
    resource_uri_template: str | None = None
    handler: ActionHandler | None = None

    @property
    def input_schema(self) -> dict[str, Any]:
        return self.input_model.model_json_schema()

    def to_spec(self) -> AgentActionSpecOut:
        return AgentActionSpecOut(
            name=self.name,
            title=self.title,
            description=self.description,
            input_schema=self.input_schema,
            output_schema=self.output_schema,
            permission_scope=self.permission_scope,
            is_destructive=self.is_destructive,
            tags=self.tags,
            resource_uri_template=self.resource_uri_template,
        )


class AgentActionRegistry:
    def __init__(self) -> None:
        self._actions: dict[str, SmartRAGAction] = {}

    def register(self, action: SmartRAGAction) -> None:
        if action.name in self._actions:
            raise ValueError(f"Duplicate SmartRAG action: {action.name}")
        if not action.handler:
            raise ValueError(f"SmartRAG action {action.name} has no handler")
        self._actions[action.name] = action

    def get(self, name: str) -> SmartRAGAction:
        try:
            return self._actions[name]
        except KeyError as exc:
            raise KeyError(f"Unknown SmartRAG action: {name}") from exc

    def list(self, names: Iterable[str] | None = None) -> list[SmartRAGAction]:
        if names is None:
            return [self._actions[key] for key in sorted(self._actions)]
        selected = []
        for name in names:
            if name in self._actions:
                selected.append(self._actions[name])
        return selected


action_registry = AgentActionRegistry()


def _normalize_description(func: Callable[..., Any], explicit: str | None, *, is_destructive: bool) -> str:
    base = inspect.cleandoc(explicit or inspect.getdoc(func) or "")
    side_effect = (
        "Side effects: destructive write operation; may update or delete persisted SmartRAG resources."
        if is_destructive
        else "Side effects: read-only unless the description explicitly says it starts a run or creates a resource."
    )
    if "Side effects:" not in base:
        base = f"{base}\n\n{side_effect}" if base else side_effect
    return base


def smartrag_action(
    *,
    name: str,
    title: str,
    input_model: type[BaseModel] = EmptyActionInput,
    output_schema: dict[str, Any] | None = None,
    permission_scope: str = "read",
    is_destructive: bool = False,
    tags: list[str] | None = None,
    resource_uri_template: str | None = None,
    description: str | None = None,
) -> Callable[[ActionHandler], ActionHandler]:
    def decorator(func: ActionHandler) -> ActionHandler:
        action_registry.register(
            SmartRAGAction(
                name=name,
                title=title,
                description=_normalize_description(func, description, is_destructive=is_destructive),
                input_model=input_model,
                output_schema=output_schema or {},
                permission_scope=permission_scope,
                is_destructive=is_destructive,
                tags=tags or [],
                resource_uri_template=resource_uri_template,
                handler=func,
            )
        )
        return func

    return decorator


def _unwrap_tool_arguments(input_data: dict[str, Any] | BaseModel | None) -> dict[str, Any] | BaseModel | None:
    if isinstance(input_data, BaseModel) or not isinstance(input_data, dict):
        return input_data
    if set(input_data.keys()) != {"arguments"}:
        return input_data
    arguments = input_data["arguments"]
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "Do not wrap tool arguments in an `arguments` field; pass schema fields at the top level. "
                "If an `arguments` field is used, it must contain a valid JSON object string."
            ) from exc
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("Do not wrap tool arguments in an `arguments` field; pass schema fields at the top level.")


async def execute_action(
    name: str,
    input_data: dict[str, Any] | BaseModel | None,
    context: AgentActionContext,
) -> AgentActionResult:
    action = action_registry.get(name)
    assert action.handler is not None
    try:
        normalized_input = _unwrap_tool_arguments(input_data)
        payload = (
            normalized_input
            if isinstance(normalized_input, BaseModel)
            else action.input_model.model_validate(normalized_input or {})
        )
        output = await action.handler(context, payload)
    except Exception as exc:
        return AgentActionResult(action_name=name, ok=False, error=str(exc))
    return AgentActionResult(action_name=name, ok=True, output=jsonable_encoder(output))


def list_action_specs() -> list[AgentActionSpecOut]:
    return [action.to_spec() for action in action_registry.list()]
