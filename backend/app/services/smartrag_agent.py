from __future__ import annotations

import asyncio
import json
import logging
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
from app.observability import flush_langfuse, get_langchain_callback_handler
from app.db.session import AsyncSessionLocal
from app.models.entities import (
    AgentProfile,
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
from app.services import chunks, parse_runs, vectors


_RUNNING_AGENT_TASKS: dict[str, asyncio.Task[None]] = {}
_AGENT_EVENT_SUBSCRIBERS: dict[str, set[asyncio.Queue[tuple[int, str, str]]]] = {}
TERMINAL_AGENT_STATUSES = {"completed", "failed", "cancelled"}
SMART_RAG_AGENT_RECURSION_LIMIT = 200
logger = logging.getLogger(__name__)


def _error_text(exc: BaseException) -> str:
    text = str(exc).strip()
    return text or exc.__class__.__name__


SMART_RAG_AGENT_SYSTEM_PROMPT = """You are SmartRAG Agent, the operational assistant for a modular RAG platform.

Use tools when you need current project state, run traces, parsed content, chunk details, vector index details, RAG flow results, or evaluation failures. Prefer read-only tools for inspection. Use write, delete, or run-starting tools only when the user clearly asks for that operation.

Tool call rules:
- Choose the smallest tool that answers the immediate question.
- Before destructive updates or deletes, make sure the user intent is explicit.
- Long-running create_*_run tools suspend the agent turn until they complete; do not build manual polling loops with repeated get_*_run calls.
- If a tool fails, explain the recoverable next step from the error instead of retrying blindly.
- Pass tool arguments as top-level JSON fields that match the tool schema. Do not wrap them in an "arguments" object.

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
        langfuse_trace_id=row.langfuse_trace_id,
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
    schedule_agent_run(run.run_id)
    return _agent_run_out(run)


def schedule_agent_run(run_id: str) -> None:
    task = asyncio.create_task(execute_agent_run(run_id))
    _RUNNING_AGENT_TASKS[run_id] = task
    task.add_done_callback(lambda done_task: _handle_agent_task_done(run_id, done_task))


def _handle_agent_task_done(run_id: str, task: asyncio.Task[None]) -> None:
    _RUNNING_AGENT_TASKS.pop(run_id, None)
    if task.cancelled():
        return
    exc = task.exception()
    if not exc:
        return
    logger.exception("Unhandled SmartRAG Agent task error for run %s", run_id, exc_info=exc)
    try:
        asyncio.create_task(_fail_agent_run(run_id, str(exc)))
    except RuntimeError:
        logger.exception("Failed to schedule SmartRAG Agent failure persistence for run %s", run_id)


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


async def list_agent_runs(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
) -> list[AgentRunOut]:
    rows = (
        await session.scalars(
            select(SmartRagAgentRun)
            .options(selectinload(SmartRagAgentRun.tool_logs), selectinload(SmartRagAgentRun.events))
            .order_by(SmartRagAgentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
    ).all()
    return [_agent_run_out(row) for row in rows]


async def delete_agent_run(session: AsyncSession, run_id: str) -> None:
    run = await session.get(SmartRagAgentRun, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SmartRAG Agent run not found")
    if run.status in {"pending", "running"}:
        task = _RUNNING_AGENT_TASKS.get(run_id)
        if task and not task.done():
            task.cancel()
    await session.delete(run)
    await session.commit()


async def _mark_run_cancelled(session: AsyncSession, run_id: str, reason: str = "Agent run cancelled by user.") -> SmartRagAgentRun:
    run = await get_agent_run_model(session, run_id)
    if run.status in TERMINAL_AGENT_STATUSES:
        return run
    await append_event(session, run_id, "run_cancelled", {"reason": reason})
    run.status = "cancelled"
    run.error = reason
    run.ended_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)
    return run


async def _mark_run_failed(session: AsyncSession, run_id: str, error: str) -> SmartRagAgentRun:
    run = await get_agent_run_model(session, run_id)
    if run.status in TERMINAL_AGENT_STATUSES:
        return run
    await append_event(session, run_id, "run_error", {"error": error})
    run.status = "failed"
    run.error = error
    run.ended_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(run)
    return run


async def _fail_agent_run(run_id: str, error: str) -> None:
    try:
        async with AsyncSessionLocal() as session:
            await _mark_run_failed(session, run_id, error)
    except Exception:
        logger.exception("Failed to persist SmartRAG Agent failure for run %s", run_id)


async def cancel_agent_run(session: AsyncSession, run_id: str) -> AgentRunOut:
    run = await get_agent_run_model(session, run_id)
    if run.status in TERMINAL_AGENT_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent run is already {run.status} and cannot be cancelled.",
        )
    task = _RUNNING_AGENT_TASKS.get(run_id)
    if task and not task.done():
        task.cancel()
    cancelled = await _mark_run_cancelled(session, run_id)
    return _agent_run_out(cancelled)


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
    _publish_agent_event(event)
    return event


def _agent_event_to_sse(row: SmartRagAgentRunEvent) -> str:
    payload = AgentRunEventOut.model_validate(row, from_attributes=True).model_dump(mode="json")
    return f"event: {row.event_type}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _publish_agent_event(row: SmartRagAgentRunEvent) -> None:
    subscribers = _AGENT_EVENT_SUBSCRIBERS.get(row.run_id)
    if not subscribers:
        return
    message = (row.sequence, row.event_type, _agent_event_to_sse(row))
    for queue in list(subscribers):
        queue.put_nowait(message)


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


def _extract_reasoning_delta(chunk: Any) -> str | None:
    additional = getattr(chunk, "additional_kwargs", {}) or {}
    for key in ("reasoning_content", "reasoning", "reasoning_summary"):
        value = additional.get(key)
        if value:
            return str(value)
    content = getattr(chunk, "content", None)
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") in {"reasoning", "reasoning_summary"}:
                value = block.get("summary") or block.get("text")
                if value:
                    parts.append(str(value))
        if parts:
            return "\n".join(parts)
    return None


def _extract_final_answer(result: Any) -> str:
    messages = result.get("messages", []) if isinstance(result, dict) else []
    if messages:
        return _extract_message_text(messages[-1])
    return _extract_message_text(result)


def _model_summary(model: ModelConnection) -> dict[str, Any]:
    return {
        "model_id": model.model_id,
        "display_name": model.display_name,
        "provider": model.provider,
        "model_name": model.model_name,
        "model_category": model.model_category,
        "enabled": model.enabled,
        "connection_status": model.connection_status,
        "supports_tools": model.supports_tools,
    }


def _agent_profile_summary(agent: AgentProfile) -> dict[str, Any]:
    return {
        "agent_id": agent.agent_id,
        "agent_name": agent.agent_name,
        "agent_type": agent.agent_type,
        "model_id": agent.model_id,
        "dry_run_status": agent.dry_run_status,
        "enabled": agent.enabled,
    }


async def build_project_context(session: AsyncSession) -> str:
    models = (
        await session.scalars(select(ModelConnection).where(ModelConnection.enabled.is_(True)).order_by(ModelConnection.created_at.desc()))
    ).all()
    llms = [_model_summary(model) for model in models if model.model_category != "embedding"]
    embeddings = [_model_summary(model) for model in models if model.model_category == "embedding"]
    agent_profiles = (
        await session.scalars(select(AgentProfile).where(AgentProfile.enabled.is_(True)).order_by(AgentProfile.created_at.desc()))
    ).all()
    parser_items = [
        {
            "parser_name": item.parser_name,
            "supported_file_exts": item.supported_file_exts,
            "default_config": item.default_config,
            "availability_status": item.availability_status,
        }
        for item in await parse_runs.list_parser_strategies()
    ]
    chunker_items = [
        {
            "chunker_name": item.chunker_name,
            "requires_embedding_model": item.requires_embedding_model,
            "default_config": item.default_config,
            "availability_status": item.availability_status,
        }
        for item in await chunks.list_chunk_strategies()
    ]
    vectordb_items = [
        {
            "vectordb_name": item.vectordb_name,
            "default_config": item.default_config,
            "availability_status": item.availability_status,
        }
        for item in await vectors.list_vectordbs()
    ]
    payload = {
        "available_llm_models": llms,
        "available_embedding_models": embeddings,
        "available_agent_profiles": [_agent_profile_summary(agent) for agent in agent_profiles],
        "available_parser_strategies": parser_items,
        "available_chunker_strategies": chunker_items,
        "available_vectordbs": vectordb_items,
    }
    return (
        "SmartRAG Project Context:\n"
        f"{json.dumps(payload, ensure_ascii=False, default=str)}\n\n"
        "Operational requirements:\n"
        "- Before create_parse_run, inspect get_parse_plan or list_parser_strategies and only use parser_name values that support the file extension.\n"
        "- Before create_vector_run, use only an available_embedding_models model_id as embedding_model_id. Never invent external model names such as openai/text-embedding-ada-002.\n"
        "- Before create_rag_flow, call get_rag_flow_build_guide, list_rag_components and list_agent_profiles. A complete RAG flow must include exactly one retrieval node and exactly one answer_generator node.\n"
        "- For RAG nodes whose component schema requires Agent Profile, use config.agent_id from available_agent_profiles or list_agent_profiles. Do not pass raw LLM model_id to agent_profile_required nodes.\n"
        "- create_component_config only manages passage_reranker, passage_filter and passage_compressor reusable configs; retrieval/query_expansion/answer_generator are configured directly in flow nodes.\n"
        "- When uncertain, observe with read-only tools first instead of creating tasks by trial and error.\n"
    )


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
                return (
                    f"Tool {_action_name} failed: {result.error}. Check the arguments and current SmartRAG state, "
                    "then choose a recoverable next step. Do not repeat an invalid `arguments` wrapper; pass schema fields at the top level."
                )

        tools.append(
            StructuredTool.from_function(
                coroutine=_call_tool,
                name=action.name,
                description=action.description,
                args_schema=action.input_model,
            )
        )
    return tools


def _get_handler_trace_id(handler: Any) -> str:
    """Extract trace_id from a Langfuse CallbackHandler after it has been used."""
    if handler is None:
        return ""
    # langfuse v2+: get_trace_id() method
    if hasattr(handler, "get_trace_id"):
        try:
            return handler.get_trace_id() or ""
        except Exception:
            pass
    # fallback: handler.trace.id (populated after first callback fires)
    if hasattr(handler, "trace") and handler.trace:
        try:
            return handler.trace.id or ""
        except Exception:
            pass
    # fallback: handler.trace_id attribute
    if hasattr(handler, "trace_id"):
        try:
            return handler.trace_id or ""
        except Exception:
            pass
    return ""


async def execute_agent_run(run_id: str) -> None:
    try:
        from langchain.agents import create_agent
        from langchain_openai import ChatOpenAI
    except Exception as exc:
        await _fail_agent_run(run_id, f"LangChain dependencies are not available: {exc}")
        return

    lf_handler = None
    try:
        async with AsyncSessionLocal() as session:
            run = await get_agent_run_model(session, run_id)
            await _get_agent_model(session, run.model_id)
            run.status = "running"
            run.started_at = datetime.now(UTC)
            await session.commit()
            await append_event(session, run_id, "message_delta", {"role": "system", "content": "SmartRAG Agent run started."})

        async with AsyncSessionLocal() as session:
            run = await get_agent_run_model(session, run_id)
            model = await _get_agent_model(session, run.model_id)
            enabled_action_names = list(run.enabled_action_names or [])
            user_message = run.message
            project_context = await build_project_context(session)
            lf_handler, _ = get_langchain_callback_handler(
                trace_name="smartrag_agent_run",
                session_id=run_id,
                metadata={
                    "run_id": run_id,
                    "model_id": model.model_id,
                    "model_name": model.model_name,
                    "enabled_action_names": enabled_action_names,
                },
                tags=["smartrag_agent"],
            )

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
            system_prompt=f"{SMART_RAG_AGENT_SYSTEM_PROMPT}\n\n{project_context}",
        )
        run_config: dict[str, Any] = {"recursion_limit": SMART_RAG_AGENT_RECURSION_LIMIT}
        if lf_handler:
            run_config["callbacks"] = [lf_handler]
        result: Any = None
        streamed_parts: list[str] = []
        async for event in agent.astream_events(
            {"messages": [{"role": "user", "content": user_message}]},
            config=run_config,
            version="v2",
        ):
            event_name = event.get("event")
            data = event.get("data") or {}
            if event_name in {"on_chat_model_stream", "on_llm_stream"}:
                chunk = data.get("chunk")
                reasoning_delta = _extract_reasoning_delta(chunk)
                if reasoning_delta:
                    async with AsyncSessionLocal() as session:
                        await append_event(session, run_id, "reasoning_delta", {"content": reasoning_delta})
                content_delta = _extract_message_text(chunk)
                if content_delta:
                    streamed_parts.append(content_delta)
                    async with AsyncSessionLocal() as session:
                        await append_event(session, run_id, "message_delta", {"role": "assistant", "content": content_delta})
            if event_name in {"on_chain_end", "on_graph_end"} and data.get("output") is not None:
                result = data.get("output")
        answer = "".join(streamed_parts).strip()
        if not answer and result is not None:
            answer = _extract_final_answer(result)
        reasoning_summary = _extract_reasoning_summary(result) if result is not None else None
        async with AsyncSessionLocal() as session:
            run = await get_agent_run_model(session, run_id)
            if run.status == "cancelled":
                return
            if reasoning_summary:
                await append_event(session, run_id, "reasoning_delta", {"content": reasoning_summary})
            if answer and not streamed_parts:
                await append_event(session, run_id, "message_delta", {"role": "assistant", "content": answer})
            await append_event(session, run_id, "final_answer", {"answer": answer})
            run.status = "completed"
            run.answer = answer
            run.error = None
            run.ended_at = datetime.now(UTC)
            await session.commit()
        if lf_handler:
            try:
                if hasattr(lf_handler, "trace") and lf_handler.trace:
                    lf_handler.trace.update(
                        output={"answer": answer, "status": "completed"},
                        status_message="completed",
                        metadata={"run_id": run_id, "status": "completed"},
                    )
                lf_handler.flush()
            except Exception:
                logger.debug("Langfuse handler finalization failed", exc_info=True)
            # Persist trace_id (only available after callbacks have fired)
            resolved_trace_id = _get_handler_trace_id(lf_handler)
            if resolved_trace_id:
                async with AsyncSessionLocal() as session:
                    run = await get_agent_run_model(session, run_id)
                    run.langfuse_trace_id = resolved_trace_id
                    await session.commit()
    except asyncio.CancelledError:
        if lf_handler:
            try:
                if hasattr(lf_handler, "trace") and lf_handler.trace:
                    lf_handler.trace.update(
                        output={"status": "cancelled"},
                        status_message="cancelled",
                        metadata={"run_id": run_id, "status": "cancelled"},
                    )
                lf_handler.flush()
            except Exception:
                logger.debug("Langfuse handler finalization failed on cancel", exc_info=True)
            resolved_trace_id = _get_handler_trace_id(lf_handler)
        else:
            resolved_trace_id = ""
        async with AsyncSessionLocal() as session:
            run = await _mark_run_cancelled(session, run_id)
            if resolved_trace_id:
                run.langfuse_trace_id = resolved_trace_id
                await session.commit()
        raise
    except Exception as exc:
        logger.exception("SmartRAG Agent run failed for run %s", run_id)
        if lf_handler:
            try:
                if hasattr(lf_handler, "trace") and lf_handler.trace:
                    lf_handler.trace.update(
                        output={"status": "failed", "error": _error_text(exc)},
                        status_message="failed",
                        metadata={"run_id": run_id, "status": "failed"},
                    )
                lf_handler.flush()
            except Exception:
                logger.debug("Langfuse handler finalization failed on error", exc_info=True)
            resolved_trace_id = _get_handler_trace_id(lf_handler)
            if resolved_trace_id:
                async with AsyncSessionLocal() as session:
                    run = await get_agent_run_model(session, run_id)
                    run.langfuse_trace_id = resolved_trace_id
                    await session.commit()
        await _fail_agent_run(run_id, _error_text(exc))
        flush_langfuse()


async def _load_agent_event_batch(run_id: str, after_sequence: int) -> tuple[list[tuple[int, str, str]], int, bool]:
    events: list[tuple[int, str, str]] = []
    last_sequence = after_sequence
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
            events.append((row.sequence, row.event_type, _agent_event_to_sse(row)))
        should_stop = run.status in TERMINAL_AGENT_STATUSES
    return events, last_sequence, should_stop


def _log_agent_event_batch_error(run_id: str, task: asyncio.Task[tuple[list[tuple[int, str, str]], int, bool]]) -> None:
    if task.cancelled():
        return
    exc = task.exception()
    if exc:
        logger.exception("SmartRAG Agent event batch failed after stream disconnect for run %s", run_id, exc_info=exc)


async def iter_agent_events(run_id: str, after_sequence: int = 0) -> AsyncIterator[str]:
    last_sequence = after_sequence
    queue: asyncio.Queue[tuple[int, str, str]] = asyncio.Queue()
    _AGENT_EVENT_SUBSCRIBERS.setdefault(run_id, set()).add(queue)
    try:
        load_task = asyncio.create_task(_load_agent_event_batch(run_id, last_sequence))
        try:
            events, last_sequence, should_stop = await asyncio.shield(load_task)
        except asyncio.CancelledError:
            load_task.add_done_callback(lambda task: _log_agent_event_batch_error(run_id, task))
            logger.debug("SmartRAG Agent event stream disconnected for run %s", run_id)
            return
        for sequence, event_type, event in events:
            if sequence > last_sequence:
                last_sequence = sequence
            yield event
            if event_type in {"final_answer", "run_error", "run_cancelled"}:
                should_stop = True
        if should_stop:
            return

        while True:
            sequence, event_type, event = await queue.get()
            if sequence <= last_sequence:
                continue
            last_sequence = sequence
            yield event
            if event_type in {"final_answer", "run_error", "run_cancelled"}:
                return
    except asyncio.CancelledError:
        logger.debug("SmartRAG Agent event stream disconnected for run %s", run_id)
        return
    finally:
        subscribers = _AGENT_EVENT_SUBSCRIBERS.get(run_id)
        if subscribers is not None:
            subscribers.discard(queue)
            if not subscribers:
                _AGENT_EVENT_SUBSCRIBERS.pop(run_id, None)
