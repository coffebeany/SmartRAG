from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas.models import HealthCheckOut, ModelCreate, ModelDefaultsOut, ModelDefaultsUpdate, ModelOut, ModelUpdate
from app.services import models as model_service

router = APIRouter()


@router.get("/models", response_model=list[ModelOut])
async def list_models(session: AsyncSession = Depends(get_session)) -> list[ModelOut]:
    return await model_service.list_models(session)


@router.post("/models", response_model=ModelOut, status_code=status.HTTP_201_CREATED)
async def create_model(payload: ModelCreate, session: AsyncSession = Depends(get_session)) -> ModelOut:
    return await model_service.create_model(session, payload)


@router.post("/models/test-connection", response_model=HealthCheckOut)
async def test_model_config(payload: ModelCreate) -> HealthCheckOut:
    return await model_service.test_model_config(payload)


@router.get("/models/{model_id}", response_model=ModelOut)
async def get_model(model_id: str, session: AsyncSession = Depends(get_session)) -> ModelOut:
    return model_service.to_model_out(await model_service.get_model(session, model_id))


@router.patch("/models/{model_id}", response_model=ModelOut)
async def update_model(model_id: str, payload: ModelUpdate, session: AsyncSession = Depends(get_session)) -> ModelOut:
    return await model_service.update_model(session, model_id, payload)


@router.delete("/models/{model_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model(model_id: str, session: AsyncSession = Depends(get_session)) -> None:
    await model_service.delete_model(session, model_id)


@router.post("/models/{model_id}/test-connection", response_model=HealthCheckOut)
async def test_connection(model_id: str, session: AsyncSession = Depends(get_session)) -> HealthCheckOut:
    return await model_service.test_model_connection(session, model_id)


@router.post("/models/{model_id}/test-draft-connection", response_model=HealthCheckOut)
async def test_draft_connection(
    model_id: str,
    payload: ModelUpdate,
    session: AsyncSession = Depends(get_session),
) -> HealthCheckOut:
    return await model_service.test_model_draft_update(session, model_id, payload)


@router.get("/model-defaults", response_model=ModelDefaultsOut)
async def get_model_defaults(session: AsyncSession = Depends(get_session)) -> ModelDefaultsOut:
    return await model_service.get_model_defaults(session)


@router.patch("/model-defaults", response_model=ModelDefaultsOut)
async def update_model_defaults(payload: ModelDefaultsUpdate, session: AsyncSession = Depends(get_session)) -> ModelDefaultsOut:
    return await model_service.update_model_defaults(session, payload)
