from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.rag import (
    ComponentConfigCreate,
    ComponentConfigOut,
    ComponentConfigUpdate,
    RagComponentOut,
    RagFlowCreate,
    RagFlowOut,
    RagFlowRunCreate,
    RagFlowRunOut,
    RagFlowRunSummaryOut,
    RagFlowUpdate,
)
from app.services import rag as rag_service

router = APIRouter()


@router.get("/rag-components", response_model=list[RagComponentOut])
async def list_rag_components(node_type: str | None = Query(default=None)) -> list[RagComponentOut]:
    return await rag_service.list_rag_components(node_type)


@router.get("/component-configs", response_model=list[ComponentConfigOut])
async def list_component_configs(
    node_type: str | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[ComponentConfigOut]:
    return await rag_service.list_component_configs(session, node_type)


@router.post("/component-configs", response_model=ComponentConfigOut, status_code=status.HTTP_201_CREATED)
async def create_component_config(
    payload: ComponentConfigCreate,
    session: AsyncSession = Depends(get_session),
) -> ComponentConfigOut:
    return await rag_service.create_component_config(session, payload)


@router.patch("/component-configs/{config_id}", response_model=ComponentConfigOut)
async def update_component_config(
    config_id: str,
    payload: ComponentConfigUpdate,
    session: AsyncSession = Depends(get_session),
) -> ComponentConfigOut:
    return await rag_service.update_component_config(session, config_id, payload)


@router.delete("/component-configs/{config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_component_config(config_id: str, session: AsyncSession = Depends(get_session)) -> None:
    await rag_service.delete_component_config(session, config_id)


@router.get("/rag-flows", response_model=list[RagFlowOut])
async def list_rag_flows(session: AsyncSession = Depends(get_session)) -> list[RagFlowOut]:
    return await rag_service.list_rag_flows(session)


@router.post("/rag-flows", response_model=RagFlowOut, status_code=status.HTTP_201_CREATED)
async def create_rag_flow(payload: RagFlowCreate, session: AsyncSession = Depends(get_session)) -> RagFlowOut:
    return await rag_service.create_rag_flow(session, payload)


@router.get("/rag-flows/{flow_id}", response_model=RagFlowOut)
async def get_rag_flow(flow_id: str, session: AsyncSession = Depends(get_session)) -> RagFlowOut:
    return await rag_service.get_rag_flow(session, flow_id)


@router.patch("/rag-flows/{flow_id}", response_model=RagFlowOut)
async def update_rag_flow(
    flow_id: str,
    payload: RagFlowUpdate,
    session: AsyncSession = Depends(get_session),
) -> RagFlowOut:
    return await rag_service.update_rag_flow(session, flow_id, payload)


@router.delete("/rag-flows/{flow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rag_flow(flow_id: str, session: AsyncSession = Depends(get_session)) -> None:
    await rag_service.delete_rag_flow(session, flow_id)


@router.post("/rag-flows/{flow_id}/run", response_model=RagFlowRunOut, status_code=status.HTTP_201_CREATED)
async def run_rag_flow(
    flow_id: str,
    payload: RagFlowRunCreate,
    session: AsyncSession = Depends(get_session),
) -> RagFlowRunOut:
    return await rag_service.run_rag_flow(session, flow_id, payload)


@router.get("/rag-flow-runs", response_model=list[RagFlowRunSummaryOut])
async def list_rag_flow_runs(
    flow_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[RagFlowRunSummaryOut]:
    return await rag_service.list_rag_flow_runs(session, flow_id=flow_id, limit=limit, offset=offset)


@router.get("/rag-flow-runs/{run_id}", response_model=RagFlowRunOut)
async def get_rag_flow_run(run_id: str, session: AsyncSession = Depends(get_session)) -> RagFlowRunOut:
    return await rag_service.get_rag_flow_run(session, run_id)


@router.delete("/rag-flow-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rag_flow_run(run_id: str, session: AsyncSession = Depends(get_session)) -> None:
    await rag_service.delete_rag_flow_run(session, run_id)
