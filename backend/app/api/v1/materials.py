from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.materials import (
    MaterialBatchCreate,
    MaterialBatchOut,
    MaterialBatchUpdate,
    MaterialBatchVersionOut,
    MaterialFileOut,
    ParserStrategyOut,
    ParseFileRunDetailOut,
    ParseFileRunOut,
    ParsePlanOut,
    ParseRunCreate,
    ParseRunOut,
    ProcessingDefaultRuleOut,
    ProcessingDefaultRulesUpdate,
    UploadFilesOut,
)
from app.services import materials as material_service
from app.services import parse_runs as parse_run_service

router = APIRouter()


@router.get("/material-batches", response_model=list[MaterialBatchOut])
async def list_material_batches(session: AsyncSession = Depends(get_session)) -> list[MaterialBatchOut]:
    return await material_service.list_batches(session)


@router.post("/material-batches", response_model=MaterialBatchOut, status_code=status.HTTP_201_CREATED)
async def create_material_batch(
    payload: MaterialBatchCreate, session: AsyncSession = Depends(get_session)
) -> MaterialBatchOut:
    return await material_service.create_batch(session, payload)


@router.get("/material-batches/{batch_id}", response_model=MaterialBatchOut)
async def get_material_batch(
    batch_id: str, session: AsyncSession = Depends(get_session)
) -> MaterialBatchOut:
    return MaterialBatchOut.model_validate(
        await material_service.get_batch(session, batch_id), from_attributes=True
    )


@router.patch("/material-batches/{batch_id}", response_model=MaterialBatchOut)
async def update_material_batch(
    batch_id: str, payload: MaterialBatchUpdate, session: AsyncSession = Depends(get_session)
) -> MaterialBatchOut:
    return await material_service.update_batch(session, batch_id, payload)


@router.delete("/material-batches/{batch_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_material_batch(
    batch_id: str, session: AsyncSession = Depends(get_session)
) -> None:
    await material_service.delete_batch(session, batch_id)


@router.get("/material-batches/{batch_id}/files", response_model=list[MaterialFileOut])
async def list_material_files(
    batch_id: str, session: AsyncSession = Depends(get_session)
) -> list[MaterialFileOut]:
    return await material_service.list_files(session, batch_id)


@router.post("/material-batches/{batch_id}/files", response_model=UploadFilesOut)
async def upload_material_files(
    batch_id: str,
    files: list[UploadFile] = File(...),
    session: AsyncSession = Depends(get_session),
) -> UploadFilesOut:
    return await material_service.upload_files(session, batch_id, files)


@router.delete(
    "/material-batches/{batch_id}/files/{file_id}", response_model=MaterialBatchVersionOut
)
async def remove_material_file(
    batch_id: str, file_id: str, session: AsyncSession = Depends(get_session)
) -> MaterialBatchVersionOut:
    return await material_service.remove_file(session, batch_id, file_id)


@router.get("/material-batches/{batch_id}/versions", response_model=list[MaterialBatchVersionOut])
async def list_material_versions(
    batch_id: str, session: AsyncSession = Depends(get_session)
) -> list[MaterialBatchVersionOut]:
    return await material_service.list_versions(session, batch_id)


@router.get("/processing-default-rules", response_model=list[ProcessingDefaultRuleOut])
async def list_processing_default_rules(
    session: AsyncSession = Depends(get_session),
) -> list[ProcessingDefaultRuleOut]:
    return await material_service.list_processing_rules(session)


@router.patch("/processing-default-rules", response_model=list[ProcessingDefaultRuleOut])
async def update_processing_default_rules(
    payload: ProcessingDefaultRulesUpdate,
    session: AsyncSession = Depends(get_session),
) -> list[ProcessingDefaultRuleOut]:
    return await material_service.update_processing_rules(session, payload)


@router.get("/parser-strategies", response_model=list[ParserStrategyOut])
async def list_parser_strategies(
    session: AsyncSession = Depends(get_session),
) -> list[ParserStrategyOut]:
    return await material_service.list_parser_strategies(session)


@router.get("/material-batches/{batch_id}/parse-plan", response_model=ParsePlanOut)
async def get_parse_plan(
    batch_id: str, session: AsyncSession = Depends(get_session)
) -> ParsePlanOut:
    return await parse_run_service.get_parse_plan(session, batch_id)


@router.post("/parse-runs", response_model=ParseRunOut, status_code=status.HTTP_201_CREATED)
async def create_parse_run(
    payload: ParseRunCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> ParseRunOut:
    run = await parse_run_service.create_parse_run(session, payload)
    background_tasks.add_task(parse_run_service.execute_parse_run, run.run_id)
    return run


@router.get("/parse-runs", response_model=list[ParseRunOut])
async def list_parse_runs(session: AsyncSession = Depends(get_session)) -> list[ParseRunOut]:
    return await parse_run_service.list_parse_runs(session)


@router.get("/parse-runs/{run_id}", response_model=ParseRunOut)
async def get_parse_run(run_id: str, session: AsyncSession = Depends(get_session)) -> ParseRunOut:
    return await parse_run_service.get_parse_run(session, run_id)


@router.get("/parse-runs/{run_id}/files", response_model=list[ParseFileRunOut])
async def list_parse_file_runs(
    run_id: str, session: AsyncSession = Depends(get_session)
) -> list[ParseFileRunOut]:
    return await parse_run_service.list_parse_file_runs(session, run_id)


@router.get("/parse-runs/{run_id}/files/{file_run_id}", response_model=ParseFileRunDetailOut)
async def get_parse_file_run_detail(
    run_id: str, file_run_id: str, session: AsyncSession = Depends(get_session)
) -> ParseFileRunDetailOut:
    return await parse_run_service.get_parse_file_run_detail(session, run_id, file_run_id)
