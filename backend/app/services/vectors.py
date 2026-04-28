from __future__ import annotations

import hashlib
import importlib
import math
import time
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.clients.base import ModelClientConfig
from app.clients.factory import create_model_client
from app.core.security import decrypt_secret
from app.db.session import AsyncSessionLocal
from app.models.entities import (
    Chunk,
    ChunkFileRun,
    MaterialFile,
    ModelConnection,
    VectorFileRun,
    VectorItem,
    VectorRun,
    VectorRunEvent,
)
from app.schemas.materials import MaterialBatchOut
from app.schemas.vectors import (
    VectorDBOut,
    VectorFileRunOut,
    VectorPlanFileOut,
    VectorPlanOut,
    VectorRunCompareOut,
    VectorRunCreate,
    VectorRunOut,
)
from app.services import materials as material_service
from app.services.chunks import chunk_run_out, get_chunk_run_model
from app.services.models import get_model
from app.vectorstores.adapters import VectorCollectionConfig, VectorRecord, get_vectorstore_adapter
from app.vectorstores.registry import VectorDBSpec, vectordb_registry


def vectordb_out(spec: VectorDBSpec) -> VectorDBOut:
    availability = spec.availability()
    return VectorDBOut(
        vectordb_name=spec.vectordb_name,
        display_name=spec.display_name,
        description=spec.description,
        db_type=spec.db_type,
        capabilities=list(spec.capabilities),
        config_schema=spec.config_schema,
        default_config=spec.default_config,
        advanced_options_schema=spec.advanced_options_schema,
        default_storage_uri=spec.default_storage_uri,
        source=spec.source,
        enabled=spec.enabled,
        availability_status=availability.status,
        availability_reason=availability.reason,
        required_dependencies=list(spec.required_dependencies),
    )


async def list_vectordbs() -> list[VectorDBOut]:
    return [vectordb_out(spec) for spec in vectordb_registry.list_enabled()]


async def refresh_vectordbs() -> list[VectorDBOut]:
    importlib.invalidate_caches()
    return await list_vectordbs()


def vector_run_out(run: VectorRun) -> VectorRunOut:
    return VectorRunOut.model_validate(run, from_attributes=True).model_copy(
        update={
            "batch_name": run.batch.batch_name if run.batch else None,
            "chunk_status": run.chunk_run.status if run.chunk_run else None,
        }
    )


def vector_file_run_out(file_run: VectorFileRun) -> VectorFileRunOut:
    source_file = file_run.source_file
    return VectorFileRunOut.model_validate(file_run, from_attributes=True).model_copy(
        update={"original_filename": source_file.original_filename if source_file else None}
    )


async def get_vector_run_model(session: AsyncSession, run_id: str) -> VectorRun:
    run = await session.scalar(
        select(VectorRun)
        .where(VectorRun.run_id == run_id)
        .options(
            selectinload(VectorRun.batch),
            selectinload(VectorRun.chunk_run),
            selectinload(VectorRun.embedding_model),
            selectinload(VectorRun.file_runs).selectinload(VectorFileRun.source_file),
        )
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vector run not found")
    return run


async def _chunk_file_runs_for_plan(session: AsyncSession, chunk_run_id: str) -> list[VectorPlanFileOut]:
    file_runs = (
        await session.scalars(
            select(ChunkFileRun)
            .where(ChunkFileRun.run_id == chunk_run_id)
            .options(selectinload(ChunkFileRun.source_file))
            .order_by(ChunkFileRun.created_at)
        )
    ).all()
    result: list[VectorPlanFileOut] = []
    for file_run in file_runs:
        counts = await session.execute(
            select(
                func.count(Chunk.chunk_id),
                func.coalesce(func.sum(Chunk.char_count), 0),
                func.coalesce(func.sum(Chunk.token_count), 0),
            ).where(Chunk.file_run_id == file_run.file_run_id)
        )
        chunk_count, char_count, token_count = counts.one()
        result.append(
            VectorPlanFileOut(
                chunk_file_run_id=file_run.file_run_id,
                source_file_id=file_run.source_file_id,
                original_filename=file_run.source_file.original_filename if file_run.source_file else None,
                status=file_run.status,
                chunk_count=int(chunk_count or 0),
                char_count=int(char_count or 0),
                token_count=int(token_count or 0),
            )
        )
    return result


async def get_vector_plan(session: AsyncSession, batch_id: str, chunk_run_id: str) -> VectorPlanOut:
    batch = await material_service.get_batch(session, batch_id)
    chunk_run = await get_chunk_run_model(session, chunk_run_id)
    if chunk_run.batch_id != batch_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk run does not belong to batch")
    if chunk_run.status not in {"completed", "completed_with_errors"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk run is not completed")
    return VectorPlanOut(
        batch=MaterialBatchOut.model_validate(batch, from_attributes=True),
        chunk_run=chunk_run_out(chunk_run),
        files=await _chunk_file_runs_for_plan(session, chunk_run_id),
        vectordbs=await list_vectordbs(),
    )


def _validate_vectordb(spec: VectorDBSpec) -> None:
    availability = spec.availability()
    if availability.status != "available":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"VectorDB {spec.vectordb_name} is not executable: {availability.reason}",
        )


def _validate_embedding_model(model: ModelConnection) -> None:
    if model.model_category != "embedding":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model is not an embedding model")
    if not model.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Embedding model is disabled")
    if model.connection_status == "failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Embedding model connection failed")


def _model_snapshot(model: ModelConnection) -> dict:
    return {
        "model_id": model.model_id,
        "display_name": model.display_name,
        "model_category": model.model_category,
        "provider": model.provider,
        "base_url": model.base_url,
        "model_name": model.model_name,
        "resolved_model_name": model.resolved_model_name,
        "connection_status": model.connection_status,
        "embedding_dimension": model.embedding_dimension,
        "supports_batch": model.supports_batch,
        "model_traits": model.model_traits,
    }


def _collection_name(run_id: str) -> str:
    return f"sr_vector_{run_id.replace('-', '_')}"


def _storage_uri(spec: VectorDBSpec, config: dict) -> str:
    if spec.vectordb_name == "chroma":
        return config.get("path") or spec.default_storage_uri or "storage/vectors/chroma"
    if spec.vectordb_name == "qdrant":
        return config.get("url") or config.get("path") or spec.default_storage_uri or "storage/vectors/qdrant"
    return config.get("database_url") or spec.default_storage_uri or spec.vectordb_name


async def _candidate_file_runs(session: AsyncSession, chunk_run_id: str) -> list[ChunkFileRun]:
    return list(
        (
            await session.scalars(
                select(ChunkFileRun)
                .where(ChunkFileRun.run_id == chunk_run_id, ChunkFileRun.status == "completed")
                .options(selectinload(ChunkFileRun.source_file))
                .order_by(ChunkFileRun.created_at)
            )
        ).all()
    )


def _filter_file_runs(file_runs: list[ChunkFileRun], mode: str, selected_file_ids: list[str]) -> list[ChunkFileRun]:
    if mode == "all":
        return file_runs
    if mode == "selected":
        selected = set(selected_file_ids)
        return [file_run for file_run in file_runs if file_run.source_file_id in selected]
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="test_related file selection is not implemented")


async def create_vector_run(session: AsyncSession, payload: VectorRunCreate) -> VectorRunOut:
    if payload.file_selection.mode == "test_related":
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="test_related file selection is not implemented")
    batch = await material_service.get_batch(session, payload.batch_id)
    chunk_run = await get_chunk_run_model(session, payload.chunk_run_id)
    if chunk_run.batch_id != payload.batch_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk run does not belong to batch")
    if chunk_run.status not in {"completed", "completed_with_errors"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk run is not completed")

    model = await get_model(session, payload.embedding_model_id)
    _validate_embedding_model(model)
    spec = vectordb_registry.get(payload.vectordb_name)
    if not spec:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown VectorDB: {payload.vectordb_name}")
    _validate_vectordb(spec)

    vectordb_config = spec.default_config | payload.vectordb_config
    embedding_config = {
        "normalize_embeddings": vectordb_config.get("normalize_embeddings", False),
        "embedding_batch": vectordb_config.get("embedding_batch", 100),
    } | payload.embedding_config
    index_config = {
        "similarity_metric": vectordb_config.get("similarity_metric", "cosine"),
        "metadata_mode": vectordb_config.get("metadata_mode", "full"),
    } | payload.index_config
    similarity_metric = str(index_config.get("similarity_metric") or "cosine")

    file_runs = await _candidate_file_runs(session, payload.chunk_run_id)
    selected = _filter_file_runs(
        file_runs,
        payload.file_selection.mode,
        payload.file_selection.selected_file_ids,
    )
    if not selected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No chunk files selected for vectorization")
    chunk_counts = dict(
        (
            await session.execute(
                select(Chunk.file_run_id, func.count(Chunk.chunk_id))
                .where(Chunk.run_id == payload.chunk_run_id)
                .group_by(Chunk.file_run_id)
            )
        ).all()
    )
    selected = [file_run for file_run in selected if int(chunk_counts.get(file_run.file_run_id, 0)) > 0]
    if not selected:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selected files have no chunks")

    run = VectorRun(
        batch_id=batch.batch_id,
        batch_version_id=batch.current_version_id,
        chunk_run_id=chunk_run.run_id,
        embedding_model_id=model.model_id,
        embedding_model_snapshot=_model_snapshot(model),
        vectordb_name=spec.vectordb_name,
        vectordb_config=vectordb_config,
        embedding_config=embedding_config,
        index_config=index_config,
        file_selection=payload.file_selection.model_dump(),
        collection_name="pending",
        storage_uri=_storage_uri(spec, vectordb_config),
        similarity_metric=similarity_metric,
        total_files=len(selected),
        total_chunks=sum(int(chunk_counts.get(file_run.file_run_id, 0)) for file_run in selected),
    )
    session.add(run)
    await session.flush()
    run.collection_name = str(vectordb_config.get("collection_name") or _collection_name(run.run_id))
    for file_run in selected:
        session.add(
            VectorFileRun(
                run_id=run.run_id,
                chunk_file_run_id=file_run.file_run_id,
                source_file_id=file_run.source_file_id,
                chunk_count=int(chunk_counts.get(file_run.file_run_id, 0)),
            )
        )
    session.add(
        VectorRunEvent(
            run_id=run.run_id,
            event_type="created",
            status="info",
            message="Vector run created.",
            event_metadata={"file_selection": payload.file_selection.model_dump()},
        )
    )
    await session.commit()
    return vector_run_out(await get_vector_run_model(session, run.run_id))


async def list_vector_runs(session: AsyncSession) -> list[VectorRunOut]:
    runs = (
        await session.scalars(
            select(VectorRun)
            .options(selectinload(VectorRun.batch), selectinload(VectorRun.chunk_run))
            .order_by(VectorRun.created_at.desc())
        )
    ).all()
    return [vector_run_out(run) for run in runs]


async def get_vector_run(session: AsyncSession, run_id: str) -> VectorRunOut:
    return vector_run_out(await get_vector_run_model(session, run_id))


def _client_for_model(model: ModelConnection):
    return create_model_client(
        ModelClientConfig(
            provider=model.provider,
            base_url=model.base_url,
            model_name=model.model_name,
            model_category=model.model_category,
            api_key=decrypt_secret(model.api_key_encrypted),
            timeout_seconds=model.timeout_seconds,
            max_retries=model.max_retries,
        )
    )


def _normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if not norm:
        return values
    return [value / norm for value in values]


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _chunk_metadata(run: VectorRun, file_run: VectorFileRun, chunk: Chunk, source_file: MaterialFile | None) -> dict:
    base = {
        "batch_id": run.batch_id,
        "vector_run_id": run.run_id,
        "chunk_run_id": run.chunk_run_id,
        "chunk_id": chunk.chunk_id,
        "chunk_index": chunk.chunk_index,
        "source_file_id": chunk.source_file_id,
        "original_filename": source_file.original_filename if source_file else None,
        "char_count": chunk.char_count,
        "token_count": chunk.token_count,
    }
    if run.index_config.get("metadata_mode") == "minimal":
        return base
    return base | {
        "chunk_metadata": chunk.chunk_metadata,
        "source_element_refs": chunk.source_element_refs,
        "strategy_metadata": chunk.strategy_metadata,
    }


async def _add_event(
    session: AsyncSession,
    run_id: str,
    event_type: str,
    event_status: str,
    message: str | None = None,
    metadata: dict | None = None,
) -> None:
    session.add(
        VectorRunEvent(
            run_id=run_id,
            event_type=event_type,
            status=event_status,
            message=message,
            event_metadata=metadata or {},
        )
    )


async def _recompute_run_progress(session: AsyncSession, run_id: str, errors: list[str]) -> None:
    run = await get_vector_run_model(session, run_id)
    completed = sum(1 for item in run.file_runs if item.status == "completed")
    failed = sum(1 for item in run.file_runs if item.status == "failed")
    total_vectors = sum(item.vector_count for item in run.file_runs)
    run.completed_files = completed
    run.failed_files = failed
    run.total_vectors = total_vectors
    run.stats = {
        "total_files": run.total_files,
        "completed_files": completed,
        "failed_files": failed,
        "total_chunks": run.total_chunks,
        "total_vectors": total_vectors,
        "avg_vectors_per_file": round(total_vectors / completed, 2) if completed else 0,
    }
    run.error_summary = "\n".join(errors[-5:]) if errors else None
    await session.commit()


def _collection_config(run: VectorRun, dimension: int) -> VectorCollectionConfig:
    return VectorCollectionConfig(
        collection_name=run.collection_name,
        dimension=dimension,
        similarity_metric=run.similarity_metric,
        storage_uri=run.storage_uri,
        vectordb_config=run.vectordb_config,
        index_config=run.index_config,
    )


async def execute_vector_run(run_id: str) -> None:
    async with AsyncSessionLocal() as session:
        run = await get_vector_run_model(session, run_id)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await _add_event(session, run_id, "started", "info", "Vector run started.")
        await session.commit()

    errors: list[str] = []
    collection_ready = False
    dimension: int | None = None

    async with AsyncSessionLocal() as session:
        run = await get_vector_run_model(session, run_id)
        model = await get_model(session, run.embedding_model_id)
        client = _client_for_model(model)
        adapter = get_vectorstore_adapter(run.vectordb_name)
        file_runs = (
            await session.scalars(
                select(VectorFileRun)
                .where(VectorFileRun.run_id == run_id)
                .options(selectinload(VectorFileRun.source_file))
                .order_by(VectorFileRun.created_at)
            )
        ).all()

    for file_run in file_runs:
        async with AsyncSessionLocal() as session:
            current = await session.scalar(
                select(VectorFileRun)
                .where(VectorFileRun.file_run_id == file_run.file_run_id)
                .options(selectinload(VectorFileRun.run), selectinload(VectorFileRun.source_file))
            )
            if not current:
                continue
            current.status = "running"
            current.started_at = datetime.now(UTC)
            await _add_event(
                session,
                run_id,
                "file_started",
                "info",
                "Vectorizing file.",
                {"source_file_id": current.source_file_id},
            )
            await session.commit()
            started = time.perf_counter()
            try:
                chunks = (
                    await session.scalars(
                        select(Chunk)
                        .where(Chunk.file_run_id == current.chunk_file_run_id)
                        .order_by(Chunk.chunk_index)
                    )
                ).all()
                records: list[VectorRecord] = []
                item_payloads: list[dict] = []
                for chunk in chunks:
                    result = await client.embedding(chunk.contents)
                    embedding = [float(value) for value in (result.data or [])]
                    if current.run.embedding_config.get("normalize_embeddings"):
                        embedding = _normalize(embedding)
                    if not embedding:
                        raise ValueError(f"Embedding result is empty for chunk {chunk.chunk_id}")
                    if dimension is None:
                        dimension = len(embedding)
                        current.run.embedding_dimension = dimension
                        config = _collection_config(current.run, dimension)
                        await adapter.ensure_collection(config)
                        collection_ready = True
                        await _add_event(
                            session,
                            run_id,
                            "collection_ready",
                            "info",
                            "Vector collection is ready.",
                            {"collection_name": current.run.collection_name, "dimension": dimension},
                        )
                    metadata = _chunk_metadata(current.run, current, chunk, current.source_file)
                    records.append(
                        VectorRecord(
                            vector_id=chunk.chunk_id,
                            text=chunk.contents,
                            embedding=embedding,
                            metadata=metadata,
                        )
                    )
                    item_payloads.append(
                        {
                            "chunk_id": chunk.chunk_id,
                            "source_file_id": chunk.source_file_id,
                            "vector_id": chunk.chunk_id,
                            "content_hash": _content_hash(chunk.contents),
                            "embedding_dimension": len(embedding),
                            "item_metadata": metadata,
                        }
                    )
                if records:
                    if not collection_ready or dimension is None:
                        dimension = len(records[0].embedding)
                        await adapter.ensure_collection(_collection_config(current.run, dimension))
                        collection_ready = True
                    batch_size = int(current.run.embedding_config.get("embedding_batch") or 100)
                    for start in range(0, len(records), max(batch_size, 1)):
                        await adapter.upsert_vectors(
                            _collection_config(current.run, dimension),
                            records[start : start + max(batch_size, 1)],
                        )
                    for item_payload in item_payloads:
                        session.add(
                            VectorItem(
                                run_id=run_id,
                                file_run_id=current.file_run_id,
                                **item_payload,
                            )
                        )
                current.status = "completed"
                current.vector_count = len(records)
                current.failed_vectors = 0
                current.latency_ms = int((time.perf_counter() - started) * 1000)
                current.error = None
                current.ended_at = datetime.now(UTC)
                await _add_event(
                    session,
                    run_id,
                    "file_completed",
                    "success",
                    "File vectorized.",
                    {"source_file_id": current.source_file_id, "vector_count": len(records)},
                )
            except Exception as exc:
                current.status = "failed"
                current.failed_vectors = current.chunk_count
                current.latency_ms = int((time.perf_counter() - started) * 1000)
                current.error = str(exc)
                current.ended_at = datetime.now(UTC)
                file_name = current.source_file.original_filename if current.source_file else current.source_file_id
                errors.append(f"{file_name}: {exc}")
                await _add_event(
                    session,
                    run_id,
                    "file_failed",
                    "failed",
                    str(exc),
                    {"source_file_id": current.source_file_id},
                )
            await session.commit()
        async with AsyncSessionLocal() as session:
            await _recompute_run_progress(session, run_id, errors)

    async with AsyncSessionLocal() as session:
        run = await get_vector_run_model(session, run_id)
        if run.failed_files == run.total_files:
            run.status = "failed"
        elif run.failed_files:
            run.status = "completed_with_errors"
        else:
            run.status = "completed"
        run.ended_at = datetime.now(UTC)
        await _add_event(
            session,
            run_id,
            "completed",
            "success" if run.status == "completed" else "failed",
            "Vector run completed.",
            {"status": run.status, "total_vectors": run.total_vectors},
        )
        await session.commit()


async def list_vector_file_runs(session: AsyncSession, run_id: str) -> list[VectorFileRunOut]:
    await get_vector_run_model(session, run_id)
    rows = (
        await session.scalars(
            select(VectorFileRun)
            .where(VectorFileRun.run_id == run_id)
            .options(selectinload(VectorFileRun.source_file))
            .order_by(VectorFileRun.created_at)
        )
    ).all()
    return [vector_file_run_out(row) for row in rows]


async def delete_vector_run(session: AsyncSession, run_id: str) -> None:
    run = await get_vector_run_model(session, run_id)
    try:
        adapter = get_vectorstore_adapter(run.vectordb_name)
        await adapter.delete_collection(_collection_config(run, run.embedding_dimension or 0))
        await _add_event(
            session,
            run_id,
            "delete_collection",
            "success",
            "Vector collection deleted.",
            {"collection_name": run.collection_name},
        )
        await session.commit()
    except Exception as exc:
        await _add_event(session, run_id, "delete_collection", "failed", str(exc))
        run.error_summary = str(exc)
        await session.commit()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Failed to delete vector collection: {exc}") from exc
    await session.delete(run)
    await session.commit()


async def compare_batch_vector_runs(session: AsyncSession, batch_id: str) -> list[VectorRunCompareOut]:
    batch = await material_service.get_batch(session, batch_id)
    runs = (
        await session.scalars(
            select(VectorRun)
            .where(VectorRun.batch_id == batch_id)
            .order_by(VectorRun.created_at.desc())
        )
    ).all()
    return [
        VectorRunCompareOut(
            run_id=run.run_id,
            batch_id=run.batch_id,
            batch_name=batch.batch_name,
            chunk_run_id=run.chunk_run_id,
            embedding_model_id=run.embedding_model_id,
            embedding_model_name=run.embedding_model_snapshot.get("display_name"),
            vectordb_name=run.vectordb_name,
            status=run.status,
            total_files=run.total_files,
            completed_files=run.completed_files,
            failed_files=run.failed_files,
            total_chunks=run.total_chunks,
            total_vectors=run.total_vectors,
            similarity_metric=run.similarity_metric,
            embedding_dimension=run.embedding_dimension,
            stats=run.stats,
            started_at=run.started_at,
            ended_at=run.ended_at,
            created_at=run.created_at,
        )
        for run in runs
    ]
