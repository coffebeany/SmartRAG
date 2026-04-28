from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.chunks import (
    ChunkFileRunOut,
    ChunkPageOut,
    ChunkPlanOut,
    ChunkRunCompareOut,
    ChunkRunCreate,
    ChunkRunOut,
    ChunkStrategyOut,
)
from app.services import chunks as chunk_service

router = APIRouter()


@router.get("/chunk-strategies", response_model=list[ChunkStrategyOut])
async def list_chunk_strategies() -> list[ChunkStrategyOut]:
    return await chunk_service.list_chunk_strategies()


@router.post("/chunk-strategies/refresh", response_model=list[ChunkStrategyOut])
async def refresh_chunk_strategies() -> list[ChunkStrategyOut]:
    return await chunk_service.refresh_chunk_strategies()


@router.get("/material-batches/{batch_id}/chunk-plan", response_model=ChunkPlanOut)
async def get_chunk_plan(
    batch_id: str,
    parse_run_id: str = Query(...),
    session: AsyncSession = Depends(get_session),
) -> ChunkPlanOut:
    return await chunk_service.get_chunk_plan(session, batch_id, parse_run_id)


@router.post("/chunk-runs", response_model=ChunkRunOut, status_code=status.HTTP_201_CREATED)
async def create_chunk_run(
    payload: ChunkRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> ChunkRunOut:
    run = await chunk_service.create_chunk_run(session, payload)
    background_tasks.add_task(chunk_service.execute_chunk_run, run.run_id)
    return run


@router.get("/chunk-runs", response_model=list[ChunkRunOut])
async def list_chunk_runs(session: AsyncSession = Depends(get_session)) -> list[ChunkRunOut]:
    return await chunk_service.list_chunk_runs(session)


@router.get("/chunk-runs/{run_id}", response_model=ChunkRunOut)
async def get_chunk_run(run_id: str, session: AsyncSession = Depends(get_session)) -> ChunkRunOut:
    return await chunk_service.get_chunk_run(session, run_id)


@router.delete("/chunk-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chunk_run(run_id: str, session: AsyncSession = Depends(get_session)) -> None:
    await chunk_service.delete_chunk_run(session, run_id)


@router.get("/chunk-runs/{run_id}/files", response_model=list[ChunkFileRunOut])
async def list_chunk_file_runs(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> list[ChunkFileRunOut]:
    return await chunk_service.list_chunk_file_runs(session, run_id)


@router.get("/chunk-runs/{run_id}/files/{file_run_id}", response_model=ChunkFileRunOut)
async def get_chunk_file_run(
    run_id: str,
    file_run_id: str,
    session: AsyncSession = Depends(get_session),
) -> ChunkFileRunOut:
    return await chunk_service.get_chunk_file_run(session, run_id, file_run_id)


@router.get("/chunk-runs/{run_id}/files/{file_run_id}/chunks", response_model=ChunkPageOut)
async def get_chunk_file_run_chunks(
    run_id: str,
    file_run_id: str,
    offset: int = 0,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
) -> ChunkPageOut:
    return await chunk_service.get_chunk_file_run_chunks(session, run_id, file_run_id, offset, limit)


@router.get("/material-batches/{batch_id}/chunk-runs/compare", response_model=list[ChunkRunCompareOut])
async def compare_batch_chunk_runs(
    batch_id: str, session: AsyncSession = Depends(get_session)
) -> list[ChunkRunCompareOut]:
    return await chunk_service.compare_batch_chunk_runs(session, batch_id)
