from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.base import ModelClientConfig
from app.clients.factory import create_model_client
from app.core.security import decrypt_secret
from app.models.entities import AgentProfile, ModelConnection, ModelUsageEvent
from app.schemas.agents import (
    AgentDraftDryRunRequest,
    AgentDryRunOut,
    AgentDryRunRequest,
    AgentProfileCreate,
    AgentProfileOut,
    AgentProfileUpdate,
)
from app.services.catalog import default_output_schema
from app.services.models import get_model


def _render_prompt(template: str, request: AgentDryRunRequest) -> str:
    variables = {"query": request.input_text or "", "input": request.input_text or ""} | request.variables
    try:
        return template.format(**variables)
    except KeyError as exc:
        missing = exc.args[0]
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Missing prompt variable: {missing}",
        ) from exc


def _to_agent_out(agent: AgentProfile) -> AgentProfileOut:
    output = AgentProfileOut.model_validate(agent, from_attributes=True)
    if output.dry_run_status == "failed" and not output.dry_run_error:
        return output.model_copy(update={"dry_run_error": "Unknown dry-run error"})
    return output


def _exception_message(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    response_text = getattr(response, "text", None)
    if status_code:
        detail = f"HTTP {status_code}"
        if response_text:
            detail = f"{detail}: {response_text[:500]}"
        return detail
    message = str(exc).strip()
    return message or exc.__class__.__name__


async def _run_agent_prompt(
    session: AsyncSession,
    *,
    model: ModelConnection,
    prompt: str,
    runtime: dict,
    event_type: str,
    trace: dict,
) -> AgentDryRunOut:
    client = create_model_client(
        ModelClientConfig(
            provider=model.provider,
            base_url=model.base_url,
            model_name=model.model_name,
            model_category=model.model_category,
            api_key=decrypt_secret(model.api_key_encrypted),
            timeout_seconds=model.timeout_seconds,
            max_retries=model.max_retries,
        )
    )
    try:
        result = await client.chat(
            prompt,
            temperature=float(runtime.get("temperature", 0.0)),
            max_tokens=runtime.get("max_output_tokens"),
        )
        session.add(
            ModelUsageEvent(
                model_id=model.model_id,
                event_type=event_type,
                latency_ms=result.latency_ms,
                token_usage=result.token_usage,
                status="success",
            )
        )
        return AgentDryRunOut(
            status="available",
            output=result.text,
            latency_ms=result.latency_ms,
            trace=trace,
        )
    except Exception as exc:
        error = _exception_message(exc)
        session.add(
            ModelUsageEvent(
                model_id=model.model_id,
                event_type=event_type,
                status="failed",
                error=error,
            )
        )
        return AgentDryRunOut(status="failed", error=error, trace=trace)


async def list_agent_profiles(session: AsyncSession) -> list[AgentProfileOut]:
    result = await session.scalars(select(AgentProfile).order_by(AgentProfile.created_at.desc()))
    return [_to_agent_out(agent) for agent in result.all()]


async def get_agent(session: AsyncSession, agent_id: str) -> AgentProfile:
    agent = await session.scalar(select(AgentProfile).where(AgentProfile.agent_id == agent_id))
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent Profile not found")
    return agent


async def create_agent_profile(session: AsyncSession, payload: AgentProfileCreate) -> AgentProfileOut:
    await get_model(session, payload.model_id)
    agent = AgentProfile(
        project_id=payload.project_id,
        agent_name=payload.agent_name,
        agent_type=payload.agent_type,
        model_id=payload.model_id,
        prompt_template=payload.prompt_template,
        output_schema=default_output_schema(payload.agent_type),
        runtime_config=payload.runtime_config,
        enabled=payload.enabled,
    )
    session.add(agent)
    await session.commit()
    await session.refresh(agent)
    return _to_agent_out(agent)


async def update_agent_profile(
    session: AsyncSession, agent_id: str, payload: AgentProfileUpdate
) -> AgentProfileOut:
    agent = await get_agent(session, agent_id)
    updates = payload.model_dump(exclude_unset=True)
    if "model_id" in updates:
        await get_model(session, updates["model_id"])
    for key, value in updates.items():
        setattr(agent, key, value)
    if "agent_type" in updates:
        agent.output_schema = default_output_schema(updates["agent_type"])
    await session.commit()
    await session.refresh(agent)
    return _to_agent_out(agent)


async def dry_run_agent(
    session: AsyncSession, agent_id: str, request: AgentDryRunRequest
) -> AgentDryRunOut:
    agent = await get_agent(session, agent_id)
    model = await session.get(ModelConnection, agent.model_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent model not found")
    prompt = _render_prompt(agent.prompt_template, request)
    runtime = agent.runtime_config or {}
    result = await _run_agent_prompt(
        session,
        model=model,
        prompt=prompt,
        runtime=runtime,
        event_type=f"agent:{agent.agent_type}:dry_run",
        trace={"agent_id": agent.agent_id, "model_id": model.model_id},
    )
    if result.status == "available":
        agent.dry_run_status = "available"
        agent.dry_run_error = None
    else:
        agent.dry_run_status = "failed"
        agent.dry_run_error = result.error or "Unknown dry-run error"
    await session.commit()
    return result


async def dry_run_agent_draft(
    session: AsyncSession, request: AgentDraftDryRunRequest
) -> AgentDryRunOut:
    model = await session.get(ModelConnection, request.model_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent model not found")
    prompt = _render_prompt(request.prompt_template, request)
    runtime = request.runtime_config or {}
    result = await _run_agent_prompt(
        session,
        model=model,
        prompt=prompt,
        runtime=runtime,
        event_type="agent:draft:dry_run",
        trace={"model_id": model.model_id, "draft": True},
    )
    await session.commit()
    return result
