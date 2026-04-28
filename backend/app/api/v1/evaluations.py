from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.evaluations import (
    EvaluationDatasetItemsPageOut,
    EvaluationDatasetRunCreate,
    EvaluationDatasetRunOut,
    EvaluationFrameworkOut,
    EvaluationReportItemsPageOut,
    EvaluationReportRunCreate,
    EvaluationReportRunOut,
    ParseEvaluationRunCreate,
    ParseEvaluatorOut,
)
from app.services import evaluations as evaluation_service

router = APIRouter()


@router.get("/parse-evaluators", response_model=list[ParseEvaluatorOut])
async def list_parse_evaluators() -> list[ParseEvaluatorOut]:
    return await evaluation_service.list_parse_evaluators()


@router.post("/parse-evaluation-runs", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_parse_evaluation_run(payload: ParseEvaluationRunCreate) -> None:
    await evaluation_service.create_parse_evaluation_run(payload)


@router.get("/evaluation-frameworks", response_model=list[EvaluationFrameworkOut])
async def list_evaluation_frameworks() -> list[EvaluationFrameworkOut]:
    return await evaluation_service.list_evaluation_frameworks()


@router.post("/evaluation-dataset-runs", response_model=EvaluationDatasetRunOut, status_code=status.HTTP_201_CREATED)
async def create_evaluation_dataset_run(
    payload: EvaluationDatasetRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> EvaluationDatasetRunOut:
    run = await evaluation_service.create_evaluation_dataset_run(session, payload)
    background_tasks.add_task(evaluation_service.execute_evaluation_dataset_run, run.run_id)
    return run


@router.get("/evaluation-dataset-runs", response_model=list[EvaluationDatasetRunOut])
async def list_evaluation_dataset_runs(
    session: AsyncSession = Depends(get_session),
) -> list[EvaluationDatasetRunOut]:
    return await evaluation_service.list_evaluation_dataset_runs(session)


@router.get("/evaluation-dataset-runs/{run_id}", response_model=EvaluationDatasetRunOut)
async def get_evaluation_dataset_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> EvaluationDatasetRunOut:
    return await evaluation_service.get_evaluation_dataset_run(session, run_id)


@router.delete("/evaluation-dataset-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation_dataset_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    await evaluation_service.delete_evaluation_dataset_run(session, run_id)


@router.get("/evaluation-dataset-runs/{run_id}/items", response_model=EvaluationDatasetItemsPageOut)
async def list_evaluation_dataset_items(
    run_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> EvaluationDatasetItemsPageOut:
    return await evaluation_service.list_evaluation_dataset_items(session, run_id, offset, limit)


@router.post("/evaluation-report-runs", response_model=EvaluationReportRunOut, status_code=status.HTTP_201_CREATED)
async def create_evaluation_report_run(
    payload: EvaluationReportRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> EvaluationReportRunOut:
    run = await evaluation_service.create_evaluation_report_run(session, payload)
    background_tasks.add_task(evaluation_service.execute_evaluation_report_run, run.run_id)
    return run


@router.get("/evaluation-report-runs", response_model=list[EvaluationReportRunOut])
async def list_evaluation_report_runs(
    session: AsyncSession = Depends(get_session),
) -> list[EvaluationReportRunOut]:
    return await evaluation_service.list_evaluation_report_runs(session)


@router.get("/evaluation-report-runs/{run_id}", response_model=EvaluationReportRunOut)
async def get_evaluation_report_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> EvaluationReportRunOut:
    return await evaluation_service.get_evaluation_report_run(session, run_id)


@router.delete("/evaluation-report-runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evaluation_report_run(
    run_id: str,
    session: AsyncSession = Depends(get_session),
) -> None:
    await evaluation_service.delete_evaluation_report_run(session, run_id)


@router.get("/evaluation-report-runs/{run_id}/items", response_model=EvaluationReportItemsPageOut)
async def list_evaluation_report_items(
    run_id: str,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_session),
) -> EvaluationReportItemsPageOut:
    return await evaluation_service.list_evaluation_report_items(session, run_id, offset, limit)
