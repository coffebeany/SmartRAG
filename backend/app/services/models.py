from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.base import ModelClientConfig
from app.clients.factory import create_model_client
from app.core.security import decrypt_secret, encrypt_secret, mask_secret
from app.models.entities import AgentProfile, ModelConnection, ModelDefault, ModelHealthCheck
from app.schemas.models import HealthCheckOut, ModelCreate, ModelDefaultsOut, ModelDefaultsUpdate, ModelOut, ModelUpdate


def to_model_out(model: ModelConnection) -> ModelOut:
    return ModelOut.model_validate(model, from_attributes=True).model_copy(
        update={"api_key_masked": mask_secret(decrypt_secret(model.api_key_encrypted))}
    )


async def list_models(session: AsyncSession) -> list[ModelOut]:
    models = (await session.scalars(select(ModelConnection).order_by(ModelConnection.created_at.desc()))).all()
    return [to_model_out(model) for model in models]


async def get_model(session: AsyncSession, model_id: str) -> ModelConnection:
    model = await session.get(ModelConnection, model_id)
    if not model:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found")
    return model


async def create_model(session: AsyncSession, payload: ModelCreate) -> ModelOut:
    model = ModelConnection(**payload.model_dump(exclude={"api_key"}), api_key_encrypted=encrypt_secret(payload.api_key))
    session.add(model)
    await session.commit()
    await session.refresh(model)
    return to_model_out(model)


async def update_model(session: AsyncSession, model_id: str, payload: ModelUpdate) -> ModelOut:
    model = await get_model(session, model_id)
    updates = payload.model_dump(exclude_unset=True)
    api_key = updates.pop("api_key", None)
    for key, value in updates.items():
        setattr(model, key, value)
    if api_key is not None:
        model.api_key_encrypted = encrypt_secret(api_key)
    await session.commit()
    await session.refresh(model)
    return to_model_out(model)


async def delete_model(session: AsyncSession, model_id: str) -> None:
    model = await get_model(session, model_id)
    linked_agent = await session.scalar(select(AgentProfile).where(AgentProfile.model_id == model_id).limit(1))
    if linked_agent:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Model is referenced by an Agent Profile")
    await session.delete(model)
    await session.commit()


async def test_model_config(payload: ModelCreate) -> HealthCheckOut:
    config = ModelClientConfig(
        provider=payload.provider,
        base_url=payload.base_url,
        model_name=payload.model_name,
        model_category=payload.model_category,
        api_key=payload.api_key,
        timeout_seconds=payload.timeout_seconds,
        max_retries=payload.max_retries,
    )
    result = await create_model_client(config).health_check()
    return HealthCheckOut(
        status=result.status,
        latency_ms=result.latency_ms,
        error=result.error,
        response_metadata=result.metadata,
    )


async def test_model_draft_update(
    session: AsyncSession,
    model_id: str,
    payload: ModelUpdate,
) -> HealthCheckOut:
    model = await get_model(session, model_id)
    updates = payload.model_dump(exclude_unset=True)
    api_key = updates.pop("api_key", None)
    config = ModelClientConfig(
        provider=updates.get("provider", model.provider),
        base_url=updates.get("base_url", model.base_url),
        model_name=updates.get("model_name", model.model_name),
        model_category=updates.get("model_category", model.model_category),
        api_key=api_key or decrypt_secret(model.api_key_encrypted),
        timeout_seconds=updates.get("timeout_seconds", model.timeout_seconds),
        max_retries=updates.get("max_retries", model.max_retries),
    )
    result = await create_model_client(config).health_check()
    return HealthCheckOut(
        status=result.status,
        latency_ms=result.latency_ms,
        error=result.error,
        response_metadata=result.metadata,
    )


async def test_model_connection(session: AsyncSession, model_id: str) -> HealthCheckOut:
    model = await get_model(session, model_id)
    model.connection_status = "checking"
    await session.commit()

    config = ModelClientConfig(
        provider=model.provider,
        base_url=model.base_url,
        model_name=model.model_name,
        model_category=model.model_category,
        api_key=decrypt_secret(model.api_key_encrypted),
        timeout_seconds=model.timeout_seconds,
        max_retries=model.max_retries,
    )
    result = await create_model_client(config).health_check()
    model.connection_status = result.status
    model.last_check_at = datetime.now(UTC)
    model.last_error = result.error
    model.resolved_model_name = result.metadata.get("resolved_model_name", model.resolved_model_name)
    model.context_window = result.metadata.get("context_window") or model.context_window
    model.max_output_tokens = result.metadata.get("max_output_tokens") or model.max_output_tokens
    model.embedding_dimension = result.metadata.get("embedding_dimension", model.embedding_dimension)
    model.model_traits = result.metadata.get("model_traits") or model.model_traits
    for flag in ["supports_streaming", "supports_json_schema", "supports_tools", "supports_vision", "supports_batch"]:
        if isinstance(result.metadata.get(flag), bool):
            setattr(model, flag, result.metadata[flag])
    check = ModelHealthCheck(model_id=model.model_id, status=result.status, latency_ms=result.latency_ms, error=result.error, response_metadata=result.metadata)
    session.add(check)
    await session.commit()
    return HealthCheckOut(status=result.status, latency_ms=result.latency_ms, error=result.error, response_metadata=result.metadata)


async def get_model_defaults(session: AsyncSession) -> ModelDefaultsOut:
    rows = (await session.scalars(select(ModelDefault))).all()
    return ModelDefaultsOut(defaults={row.default_key: row.model_id for row in rows})


async def update_model_defaults(session: AsyncSession, payload: ModelDefaultsUpdate) -> ModelDefaultsOut:
    for key, model_id in payload.defaults.items():
        if model_id is not None:
            await get_model(session, model_id)
        existing = await session.get(ModelDefault, key)
        if existing:
            existing.model_id = model_id
        else:
            session.add(ModelDefault(default_key=key, model_id=model_id))
    await session.commit()
    return await get_model_defaults(session)
