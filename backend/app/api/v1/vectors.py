from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.vectors import (
    VectorDBOut,
    VectorFileRunOut,
    VectorPlanOut,
    VectorRunCompareOut,
    VectorRunCreate,
    VectorRunOut,
)
from app.services import vectors as vector_service

router = APIRouter()


@router.get("/vectordbs", response_model=list[VectorDBOut])
async def list_vectordbs() -> list[VectorDBOut]:
    return await vector_service.list_vectordbs()


@router.post("/vectordbs/refresh", response_model=list[VectorDBOut])
async def refresh_vectordbs() -> list[VectorDBOut]:
    return await vector_service.refresh_vectordbs()


@router.get("/material-batches/{batch_id}/vector-plan", response_model=VectorPlanOut)
async def get_vector_plan(
    batch_id: str,
    chunk_run_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> VectorPlanOut:
    return await vector_service.get_vector_plan(session, batch_id, chunk_run_id)


@router.post("/vector-runs", response_model=VectorRunOut, status_code=status.HTTP_201_CREATED)
async def create_vector_run(
    payload: VectorRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> VectorRunOut:
    run = await vector_service.create_vector_run(session, payload)
    background_tasks.add_task(vector_service.execute_vector_run, run.run_id)
    return run


@router.get("/vector-runs", response_model=list[VectorRunOut])
async def list_vector_runs(session: AsyncSession = Depends(get_session)) -> list[VectorRunOut]:
    return await vector_service.list_vector_runs(session)


@router.get("/vector-runs/{run_id}", response_model=VectorRunOut)
async def get_vector_run(run_id: str, session: AsyncSession = Depends(get_session)) -> VectorRunOut:
    return await vector_service.get_vector_run(session, run_id)


@router.delete("/vector-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vector_run(run_id: str, session: AsyncSession = Depends(get_session)) -> None:
    await vector_service.delete_vector_run(session, run_id)


@router.get("/vector-runs/{run_id}/files", response_model=list[VectorFileRunOut])
async def list_vector_file_runs(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[VectorFileRunOut]:
    return await vector_service.list_vector_file_runs(session, run_id)


@router.get("/material-batches/{batch_id}/vector-runs/compare", response_model=list[VectorRunCompareOut])
async def compare_batch_vector_runs(
    batch_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[VectorRunCompareOut]:
    return await vector_service.compare_batch_vector_runs(session, batch_id)
