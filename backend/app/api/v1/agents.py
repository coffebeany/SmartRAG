from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.agents import AgentDraftDryRunRequest, AgentDryRunOut, AgentDryRunRequest, AgentProfileCreate, AgentProfileOut, AgentProfileUpdate
from app.services import agents as agent_service

router = APIRouter()


@router.get("/agent-profiles", response_model=list[AgentProfileOut])
async def list_agent_profiles(session: AsyncSession = Depends(get_session)) -> list[AgentProfileOut]:
    return await agent_service.list_agent_profiles(session)


@router.post("/agent-profiles", response_model=AgentProfileOut, status_code=status.HTTP_201_CREATED)
async def create_agent_profile(payload: AgentProfileCreate, session: AsyncSession = Depends(get_session)) -> AgentProfileOut:
    return await agent_service.create_agent_profile(session, payload)


@router.post("/agent-profiles/dry-run", response_model=AgentDryRunOut)
async def dry_run_agent_draft(
    payload: AgentDraftDryRunRequest, session: AsyncSession = Depends(get_session)
) -> AgentDryRunOut:
    return await agent_service.dry_run_agent_draft(session, payload)


@router.get("/agent-profiles/{agent_id}", response_model=AgentProfileOut)
async def get_agent_profile(agent_id: str, session: AsyncSession = Depends(get_session)) -> AgentProfileOut:
    return agent_service._to_agent_out(await agent_service.get_agent(session, agent_id))


@router.patch("/agent-profiles/{agent_id}", response_model=AgentProfileOut)
async def update_agent_profile(agent_id: str, payload: AgentProfileUpdate, session: AsyncSession = Depends(get_session)) -> AgentProfileOut:
    return await agent_service.update_agent_profile(session, agent_id, payload)


@router.post("/agent-profiles/{agent_id}/dry-run", response_model=AgentDryRunOut)
async def dry_run_agent(agent_id: str, payload: AgentDryRunRequest, session: AsyncSession = Depends(get_session)) -> AgentDryRunOut:
    return await agent_service.dry_run_agent(session, agent_id, payload)
