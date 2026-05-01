from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.agent_actions import AgentActionSpecOut, AgentRunCreate, AgentRunOut
from app.services import smartrag_agent

router = APIRouter()


@router.get("/agent-actions", response_model=list[AgentActionSpecOut])
async def list_agent_actions() -> list[AgentActionSpecOut]:
    return await smartrag_agent.list_agent_actions()


@router.post("/smartrag-agent/runs", response_model=AgentRunOut)
async def create_agent_run(
    payload: AgentRunCreate,
    session: AsyncSession = Depends(get_session),
) -> AgentRunOut:
    return await smartrag_agent.create_agent_run(session, payload)


@router.get("/smartrag-agent/runs", response_model=list[AgentRunOut])
async def list_agent_runs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[AgentRunOut]:
    return await smartrag_agent.list_agent_runs(session, limit=limit, offset=offset)


@router.get("/smartrag-agent/runs/{run_id}", response_model=AgentRunOut)
async def get_agent_run(run_id: str, session: AsyncSession = Depends(get_session)) -> AgentRunOut:
    return await smartrag_agent.get_agent_run(session, run_id)


@router.post("/smartrag-agent/runs/{run_id}/cancel", response_model=AgentRunOut)
async def cancel_agent_run(run_id: str, session: AsyncSession = Depends(get_session)) -> AgentRunOut:
    return await smartrag_agent.cancel_agent_run(session, run_id)


@router.delete("/smartrag-agent/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent_run(run_id: str, session: AsyncSession = Depends(get_session)) -> None:
    await smartrag_agent.delete_agent_run(session, run_id)


@router.get("/smartrag-agent/runs/{run_id}/events")
async def stream_agent_run_events(
    run_id: str,
    after_sequence: int = Query(default=0, ge=0),
) -> StreamingResponse:
    return StreamingResponse(
        smartrag_agent.iter_agent_events(run_id, after_sequence=after_sequence),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
