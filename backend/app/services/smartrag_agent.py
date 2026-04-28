from __future__ import annotations

import asyncio
import json
import time
from datetime import UTC, datetime
from typing import Any, AsyncIterator

from fastapi import HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent_actions import AgentActionContext, action_registry, execute_action, list_action_specs
from app.core.security import decrypt_secret
from app.db.session import AsyncSessionLocal
from app.models.entities import (
    ModelConnection,
    SmartRagAgentRun,
    SmartRagAgentRunEvent,
    SmartRagAgentToolLog,
)
from app.schemas.agent_actions import (
    AgentActionSpecOut,
    AgentRunCreate,
    AgentRunEventOut,
    AgentRunOut,
)


SMART_RAG_AGENT_SYSTEM_PROMPT = """You are SmartRAG Agent, the operational assistant for a modular RAG platform.

Use tools when you need current project state, run traces, parsed content, chunk details, vector index details, RAG flow results, or evaluation failures. Prefer read-only tools for inspection. Use write, delete, or run-starting tools only when the user clearly asks for that operation.

Tool call rules:
- Choose the smallest tool that answers the immediate question.
- Before destructive updates or deletes, make sure the user intent is explicit.
- For long-running create_*_run tools, return the run_id and tell the user how to poll its status.
- If a tool fails, explain the recoverable next step from the error instead of retrying blindly.

Reasoning visibility:
- Do not reveal hidden chain-of-thought.
- If the model/provider emits a reasoning summary or reasoning content block, it may be surfaced as a concise summary.
"""


def _agent_run_out(row: SmartRagAgentRun) -> AgentRunOut:
    return AgentRunOut(
        run_id=row.run_id,
        model_id=row.model_id,
        message=row.message,
        enabled_action_names=list(row.enabled_action_names or []),
        status=row.status,
        answer=row.answer,
        error=row.error,
        created_at=row.created_at,
        updated_at=row.updated_at,
        started_at=row.started_at,
        ended_at=row.ended_at,
        tool_logs=jsonable_encoder(row.__dict__.get("tool_logs", [])),
        events=jsonable_encoder(row.__dict__.get("events", [])),
    )


def _chat_openai_base_url(base_url: str) -> str:
    clean = base_url.rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/embeddings"):
        if clean.endswith(suffix):
            return clean[: -len(suffix)]
    return clean


async def list_agent_actions() -> list[AgentActionSpecOut]:
    return list_action_specs()


async def _get_agent_model(session: AsyncSession, model_id: str) -> ModelConnection:
    model = await session.get(ModelConnection, model_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    if not model.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model is disabled")
    if model.provider != "openai_compatible":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SmartRAG Agent currently supports only provider=openai_compatible.",
        )
    if model.model_category == "embedding":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SmartRAG Agent requires a chat/reasoning LLM; embedding models are not supported.",
        )
    return model


async def create_agent_run(session: AsyncSession, payload: AgentRunCreate) -> AgentRunOut:
    await _get_agent_model(session, payload.model_id)
    enabled = payload.enabled_action_names
    if enabled is None:
        enabled = [action.name for action in action_registry.list()]
    unknown = sorted(set(enabled) - {action.name for action in action_registry.list()})
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown action names: {', '.join(unknown)}",
        )
    run = SmartRagAgentRun(
        model_id=payload.model_id,
        message=payload.message,
        enabled_action_names=enabled,
        status="pending",
    )
    session.add(run)
    await session.commit()
    await session.refresh(run)
    asyncio.create_task(execute_agent_run(run.run_id))
    return _agent_run_out(run)


async def get_agent_run_model(session: AsyncSession, run_id: str) -> SmartRagAgentRun:
    run = await session.scalar(
        select(SmartRagAgentRun)
        .where(SmartRagAgentRun.run_id == run_id)
        .options(selectinload(SmartRagAgentRun.tool_logs), selectinload(SmartRagAgentRun.events))
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SmartRAG Agent run not found")
    return run


async def get_agent_run(session: AsyncSession, run_id: str) -> AgentRunOut:
    return _agent_run_out(await get_agent_run_model(session, run_id))


async def _next_sequence(session: AsyncSession, run_id: str) -> int:
    current = await session.scalar(
        select(func.max(SmartRagAgentRunEvent.sequence)).where(SmartRagAgentRunEvent.run_id == run_id)
    )
    return int(current or 0) + 1


async def append_event(
    session: AsyncSession,
    run_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> SmartRagAgentRunEvent:
    event = SmartRagAgentRunEvent(
        run_id=run_id,
        event_type=event_type,
        sequence=await _next_sequence(session, run_id),
        payload=jsonable_encoder(payload),
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


def _truncate_payload(value: Any, max_chars: int = 5000) -> Any:
    encoded = jsonable_encoder(value)
    text = json.dumps(encoded, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return encoded
    return {"truncated": True, "preview": text[:max_chars], "original_chars": len(text)}


async def _record_tool_started(
    session: AsyncSession,
    run_id: str,
    tool_name: str,
    args: dict[str, Any],
) -> SmartRagAgentToolLog:
    now = datetime.now(UTC)
    row = SmartRagAgentToolLog(
        run_id=run_id,
        tool_name=tool_name,
        tool_args=jsonable_encoder(args),
        status="running",
        started_at=now,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    await append_event(
        session,
        run_id,
        "tool_call_started",
        {"tool_log_id": row.tool_log_id, "tool_name": tool_name, "args": row.tool_args, "status": "running"},
    )
    return row


async def _record_tool_result(
    session: AsyncSession,
    run_id: str,
    log_id: str,
    *,
    ok: bool,
    output: Any = None,
    error: str | None = None,
    started: float,
) -> None:
    row = await session.get(SmartRagAgentToolLog, log_id)
    if not row:
        return
    row.status = "success" if ok else "error"
    row.output = _truncate_payload(output)
    row.error = error
    row.latency_ms = int((time.perf_counter() - started) * 1000)
    row.ended_at = datetime.now(UTC)
    await session.commit()
    payload = {
        "tool_log_id": row.tool_log_id,
        "tool_name": row.tool_name,
        "status": row.status,
        "latency_ms": row.latency_ms,
        "output": row.output,
    }
    if ok:
        await append_event(session, run_id, "tool_call_result", payload)
    else:
        await append_event(session, run_id, "tool_call_error", payload | {"error": error})


def _extract_message_text(message: Any) -> str:
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") in {"text", "output_text"} and block.get("text"):
                    parts.append(str(block["text"]))
                elif block.get("type") in {"reasoning", "reasoning_summary"} and block.get("summary"):
                    parts.append(str(block["summary"]))
        return "\n".join(parts)
    return str(content or "")


def _extract_reasoning_summary(result: Any) -> str | None:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    for message in reversed(messages):
        content = getattr(message, "content", None)
        if not isinstance(content, list):
            continue
        summaries = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in {"reasoning", "reasoning_summary"}:
                value = block.get("summary") or block.get("text")
                if value:
                    summaries.append(str(value))
        if summaries:
            return "\n".join(summaries)
    return None


def _extract_final_answer(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if messages:
        return _extract_message_text(messages[-1])
    return _extract_message_text(result)


def _build_langchain_tools(run_id: str, action_names: list[str]):
    from langchain_core.tools import StructuredTool

    tools = []
    for action in action_registry.list(action_names):
        async def _call_tool(_action_name: str = action.name, **kwargs: Any) -> str:
            started = time.perf_counter()
            async with AsyncSessionLocal() as session:
                log = await _record_tool_started(session, run_id, _action_name, kwargs)
                result = await execute_action(
                    _action_name,
                    kwargs,
                    AgentActionContext(session=session, run_id=run_id, actor="smartrag_agent"),
                )
                if result.ok:
                    await _record_tool_result(
                        session,
                        run_id,
                        log.tool_log_id,
                        ok=True,
                        output=result.output,
                        started=started,
                    )
                    return json.dumps(result.output, ensure_ascii=False, default=str)
                await _record_tool_result(
                    session,
                    run_id,
                    log.tool_log_id,
                    ok=False,
                    output=None,
                    error=result.error,
                    started=started,
                )
                return f"Tool {_action_name} failed: {result.error}. Check the arguments and current SmartRAG state, then choose a recoverable next step."

        tools.append(
            StructuredTool.from_function(
                coroutine=_call_tool,
                name=action.name,
                description=action.description,
                args_schema=action.input_model,
            )
        )
    return tools


async def execute_agent_run(run_id: str) -> None:
    async with AsyncSessionLocal() as session:
        run = await get_agent_run_model(session, run_id)
        model = await _get_agent_model(session, run.model_id)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await session.commit()
        await append_event(session, run_id, "message_delta", {"role": "system", "content": "SmartRAG Agent run started."})

    try:
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI
    except Exception as exc:
        async with AsyncSessionLocal() as session:
            run = await get_agent_run_model(session, run_id)
            await append_event(session, run_id, "run_error", {"error": f"LangChain dependencies are not available: {exc}"})
            run.status = "failed"
            run.error = f"LangChain dependencies are not available: {exc}"
            run.ended_at = datetime.now(UTC)
            await session.commit()
        return

    try:
        async with AsyncSessionLocal() as session:
            run = await get_agent_run_model(session, run_id)
            model = await _get_agent_model(session, run.model_id)
            enabled_action_names = list(run.enabled_action_names or [])
            user_message = run.message

        chat_model = ChatOpenAI(
            model=model.model_name,
            base_url=_chat_openai_base_url(model.base_url),
            api_key=decrypt_secret(model.api_key_encrypted) or "not-set",
            timeout=model.timeout_seconds,
            max_retries=model.max_retries,
            temperature=0,
        )
        agent = create_agent(
            model=chat_model,
            tools=_build_langchain_tools(run_id, enabled_action_names),
            system_prompt=SMART_RAG_AGENT_SYSTEM_PROMPT,
        )
        result = await agent.ainvoke({"messages": [{"role": "user", "content": user_message}]})
        reasoning_summary = _extract_reasoning_summary(result)
        answer = _extract_final_answer(result)
        async with AsyncSessionLocal() as session:
            run = await get_agent_run_model(session, run_id)
            if reasoning_summary:
                await append_event(session, run_id, "reasoning_delta", {"content": reasoning_summary})
            if answer:
                await append_event(session, run_id, "message_delta", {"role": "assistant", "content": answer})
            await append_event(session, run_id, "final_answer", {"answer": answer})
            run.status = "completed"
            run.answer = answer
            run.error = None
            run.ended_at = datetime.now(UTC)
            await session.commit()
    except Exception as exc:
        async with AsyncSessionLocal() as session:
            run = await get_agent_run_model(session, run_id)
            await append_event(session, run_id, "run_error", {"error": str(exc)})
            run.status = "failed"
            run.error = str(exc)
            run.ended_at = datetime.now(UTC)
            await session.commit()


async def iter_agent_events(run_id: str) -> AsyncIterator[str]:
    last_sequence = 0
    while True:
        async with AsyncSessionLocal() as session:
            run = await get_agent_run_model(session, run_id)
            rows = (
                await session.scalars(
                    select(SmartRagAgentRunEvent)
                    .where(
                        SmartRagAgentRunEvent.run_id == run_id,
                        SmartRagAgentRunEvent.sequence > last_sequence,
                    )
                    .order_by(SmartRagAgentRunEvent.sequence)
                )
            ).all()
            for row in rows:
                last_sequence = row.sequence
                payload = AgentRunEventOut.model_validate(row, from_attributes=True).model_dump(mode="json")
                yield f"event: {row.event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
            if run.status in {"completed", "failed"} and not rows:
                break
        await asyncio.sleep(0.5)
