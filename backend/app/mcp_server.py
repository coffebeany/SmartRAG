from __future__ import annotations

import inspect
from typing import Any, Callable

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.agent_actions import AgentActionContext, action_registry, execute_action
from app.db.session import AsyncSessionLocal
from app.services import evaluations, parse_runs, rag


MCP_INSTRUCTIONS = """SmartRAG MCP exposes project operations through the same Agent Action Registry used by the UI Agent.

Use read-only tools first to observe batches, runs, traces, chunks, vector indexes and evaluation failures. Use destructive tools only when the user has explicitly requested the change. Long-running create_*_run tools return a run_id; poll the matching get_*_run tool or resource to observe progress.
"""


async def _call_action(action_name: str, payload: dict[str, Any] | None = None) -> Any:
    async with AsyncSessionLocal() as session:
        result = await execute_action(
            action_name,
            payload or {},
            AgentActionContext(session=session, actor="mcp"),
        )
        if not result.ok:
            return {"ok": False, "error": result.error}
        return {"ok": True, "output": result.output}


def _tool_wrapper(action_name: str) -> Callable[..., Any]:
    action = action_registry.get(action_name)

    async def tool(**kwargs: Any) -> Any:
        return await _call_action(action_name, kwargs)

    tool.__name__ = action_name
    tool.__doc__ = action.description
    parameters = []
    annotations: dict[str, Any] = {}
    for field_name, field in action.input_model.model_fields.items():
        annotation = field.annotation or Any
        annotations[field_name] = annotation
        default = inspect.Parameter.empty
        if not field.is_required():
            default = None if field.default_factory is not None else field.default
        parameters.append(
            inspect.Parameter(
                field_name,
                inspect.Parameter.KEYWORD_ONLY,
                default=default,
                annotation=annotation,
            )
        )
    tool.__annotations__ = annotations
    tool.__signature__ = inspect.Signature(parameters)  # type: ignore[attr-defined]
    return tool


def create_smartrag_mcp_app():
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        try:
            from fastmcp import FastMCP  # type: ignore
        except Exception:
            return None

    mcp = FastMCP("SmartRAG", instructions=MCP_INSTRUCTIONS)
    for action in action_registry.list():
        mcp.tool(
            name=action.name,
            description=(
                f"{action.description}\n\n"
                f"Permission scope: {action.permission_scope}. "
                f"Destructive: {'yes' if action.is_destructive else 'no'}. "
                f"Tags: {', '.join(action.tags) or 'none'}. "
                "Pass arguments according to this action's input schema."
            ),
        )(_tool_wrapper(action.name))

    async def parse_run_summary(run_id: str) -> str:
        async with AsyncSessionLocal() as session:
            return (await parse_runs.get_parse_run(session, run_id)).model_dump_json()

    async def rag_flow_run_trace(run_id: str) -> str:
        async with AsyncSessionLocal() as session:
            run = await rag.get_rag_flow_run(session, run_id)
            return run.model_dump_json()

    async def evaluation_failures(report_run_id: str) -> str:
        async with AsyncSessionLocal() as session:
            page = await evaluations.list_evaluation_report_items(session, report_run_id, 0, 500)
            failures = [
                item.model_dump(mode="json")
                for item in page.items
                if item.error or any(isinstance(value, int | float) and float(value) < 0.5 for value in item.scores.values())
            ]
            return {"report_run_id": report_run_id, "items": failures}.__repr__()

    mcp.resource(
        "smartrag://parse-runs/{run_id}/summary",
        name="Parse run summary",
        title="Parse run summary",
        description="Read-only summary for a parse run. Use to poll status and errors by run_id.",
        mime_type="application/json",
    )(parse_run_summary)
    mcp.resource(
        "smartrag://rag-flow-runs/{run_id}/trace",
        name="RAG flow run trace",
        title="RAG flow run trace",
        description="Read-only trace, final passages and answer for a RAG flow run.",
        mime_type="application/json",
    )(rag_flow_run_trace)
    mcp.resource(
        "smartrag://evaluation-report-runs/{report_run_id}/failures",
        name="Evaluation failure cases",
        title="Evaluation failure cases",
        description="Read-only failed or low-scoring evaluation report items.",
        mime_type="application/json",
    )(evaluation_failures)
    if hasattr(mcp, "streamable_http_app"):
        return mcp.streamable_http_app()
    return mcp.http_app()


def mount_mcp_server(app: FastAPI) -> None:
    mcp_app = create_smartrag_mcp_app()
    if mcp_app is not None:
        app.mount("/mcp", mcp_app)
        return

    @app.get("/mcp")
    @app.post("/mcp")
    async def mcp_unavailable() -> JSONResponse:
        return JSONResponse(
            {"detail": "MCP server dependencies are not installed. Install the mcp package to enable /mcp."},
            status_code=503,
        )
