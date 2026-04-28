from __future__ import annotations

import importlib
import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.chunkers.adapters import ParsedDocumentInput, get_adapter
from app.chunkers.registry import ChunkerStrategySpec, chunker_registry
from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.entities import (
    Chunk,
    ChunkFileRun,
    ChunkRun,
    ParsedDocument,
    ParseFileRun,
)
from app.schemas.chunks import (
    ChunkFileRunOut,
    ChunkOut,
    ChunkPageOut,
    ChunkPlanFileOut,
    ChunkPlanOut,
    ChunkRunCompareOut,
    ChunkRunCreate,
    ChunkRunOut,
    ChunkStrategyOut,
)
from app.schemas.materials import MaterialBatchOut
from app.services import materials as material_service
from app.services.parse_runs import get_parse_run_model, parse_run_out


def chunk_strategy_out(strategy: ChunkerStrategySpec) -> ChunkStrategyOut:
    availability = strategy.availability()
    return ChunkStrategyOut(
        chunker_name=strategy.chunker_name,
        display_name=strategy.display_name,
        description=strategy.description,
        module_type=strategy.module_type,
        chunk_method=strategy.chunk_method,
        capabilities=list(strategy.capabilities),
        config_schema=strategy.config_schema,
        default_config=strategy.default_config,
        source=strategy.source,
        enabled=strategy.enabled,
        availability_status=availability.status,
        availability_reason=availability.reason,
        required_dependencies=list(strategy.required_dependencies),
        requires_embedding_model=strategy.requires_embedding_model,
    )


async def list_chunk_strategies() -> list[ChunkStrategyOut]:
    return [chunk_strategy_out(strategy) for strategy in chunker_registry.list_enabled()]


async def refresh_chunk_strategies() -> list[ChunkStrategyOut]:
    importlib.invalidate_caches()
    return await list_chunk_strategies()


def chunk_run_out(run: ChunkRun) -> ChunkRunOut:
    return ChunkRunOut.model_validate(run, from_attributes=True).model_copy(
        update={
            "batch_name": run.batch.batch_name if run.batch else None,
            "parse_status": run.parse_run.status if run.parse_run else None,
        }
    )


def chunk_file_run_out(file_run: ChunkFileRun) -> ChunkFileRunOut:
    parsed = file_run.parsed_document
    source_file = parsed.file_run.file if parsed and parsed.file_run else None
    return ChunkFileRunOut.model_validate(file_run, from_attributes=True).model_copy(
        update={
            "original_filename": source_file.original_filename if source_file else None,
            "parser_name": parsed.parser_name if parsed else None,
        }
    )


async def _parsed_documents_for_run(session: AsyncSession, parse_run_id: str) -> list[ParsedDocument]:
    rows = (
        await session.scalars(
            select(ParsedDocument)
            .where(ParsedDocument.run_id == parse_run_id)
            .options(selectinload(ParsedDocument.file_run).selectinload(ParseFileRun.file))
            .order_by(ParsedDocument.created_at)
        )
    ).all()
    return list(rows)


async def get_chunk_plan(session: AsyncSession, batch_id: str, parse_run_id: str) -> ChunkPlanOut:
    batch = await material_service.get_batch(session, batch_id)
    parse_run = await get_parse_run_model(session, parse_run_id)
    if parse_run.batch_id != batch_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parse run does not belong to batch")
    if parse_run.status not in {"completed", "completed_with_errors"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parse run is not completed")
    parsed_documents = await _parsed_documents_for_run(session, parse_run_id)
    files = [
        ChunkPlanFileOut(
            parsed_document_id=document.parsed_document_id,
            file_id=document.file_id,
            original_filename=document.file_run.file.original_filename if document.file_run and document.file_run.file else None,
            parser_name=document.parser_name,
            char_count=document.char_count,
            pages=document.pages,
        )
        for document in parsed_documents
    ]
    return ChunkPlanOut(
        batch=MaterialBatchOut.model_validate(batch, from_attributes=True),
        parse_run=parse_run_out(parse_run),
        files=files,
        chunk_options=await list_chunk_strategies(),
    )


def _validate_chunker(strategy: ChunkerStrategySpec, config: dict) -> None:
    availability = strategy.availability()
    if availability.status not in {"available", "needs_config"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunker {strategy.chunker_name} is not executable: {availability.reason}",
        )
    required = strategy.config_schema.get("required", [])
    missing = [key for key in required if config.get(key) in (None, "")]
    if strategy.requires_embedding_model and config.get("embedding_model_id") in (None, ""):
        missing.append("embedding_model_id")
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Chunker {strategy.chunker_name} missing config: {', '.join(sorted(set(missing)))}",
        )


async def create_chunk_run(session: AsyncSession, payload: ChunkRunCreate) -> ChunkRunOut:
    batch = await material_service.get_batch(session, payload.batch_id)
    parse_run = await get_parse_run_model(session, payload.parse_run_id)
    if parse_run.batch_id != payload.batch_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parse run does not belong to batch")
    if parse_run.status not in {"completed", "completed_with_errors"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parse run is not completed")
    strategy = chunker_registry.get(payload.chunker_name)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown chunker: {payload.chunker_name}")
    config = strategy.default_config | payload.chunker_config
    _validate_chunker(strategy, config)
    parsed_documents = await _parsed_documents_for_run(session, payload.parse_run_id)
    if not parsed_documents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Parse run has no parsed documents")

    run = ChunkRun(
        batch_id=batch.batch_id,
        batch_version_id=batch.current_version_id,
        parse_run_id=parse_run.run_id,
        chunker_name=strategy.chunker_name,
        chunker_config=config,
        total_files=len(parsed_documents),
    )
    session.add(run)
    await session.flush()
    for document in parsed_documents:
        session.add(
            ChunkFileRun(
                run_id=run.run_id,
                parsed_document_id=document.parsed_document_id,
                source_file_id=document.file_id,
            )
        )
    await session.commit()
    refreshed = await get_chunk_run_model(session, run.run_id)
    return chunk_run_out(refreshed)


async def get_chunk_run_model(session: AsyncSession, run_id: str) -> ChunkRun:
    run = await session.scalar(
        select(ChunkRun)
        .where(ChunkRun.run_id == run_id)
        .options(
            selectinload(ChunkRun.batch),
            selectinload(ChunkRun.parse_run),
            selectinload(ChunkRun.file_runs).selectinload(ChunkFileRun.parsed_document).selectinload(ParsedDocument.file_run).selectinload(ParseFileRun.file),
        )
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk run not found")
    return run


async def list_chunk_runs(session: AsyncSession) -> list[ChunkRunOut]:
    runs = (
        await session.scalars(
            select(ChunkRun)
            .options(selectinload(ChunkRun.batch), selectinload(ChunkRun.parse_run))
            .order_by(ChunkRun.created_at.desc())
        )
    ).all()
    return [chunk_run_out(run) for run in runs]


async def get_chunk_run(session: AsyncSession, run_id: str) -> ChunkRunOut:
    return chunk_run_out(await get_chunk_run_model(session, run_id))


def _artifact_root() -> Path:
    root = Path(settings.chunk_artifact_root)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


async def delete_chunk_run(session: AsyncSession, run_id: str) -> None:
    run = await get_chunk_run_model(session, run_id)
    await session.delete(run)
    await session.commit()
    artifact_dir = _artifact_root() / run_id
    root = _artifact_root().resolve()
    resolved = artifact_dir.resolve()
    if resolved.exists() and resolved.is_dir():
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("Chunk artifact path escaped artifact root") from exc
        shutil.rmtree(resolved)


def _document_input(file_run: ChunkFileRun) -> ParsedDocumentInput:
    document = file_run.parsed_document
    file_name = document.file_run.file.original_filename if document.file_run and document.file_run.file else document.file_id
    return ParsedDocumentInput(
        parsed_document_id=document.parsed_document_id,
        source_file_id=document.file_id,
        file_name=file_name,
        text=document.text_content,
        metadata=document.document_metadata,
        elements=document.elements,
    )


def _relative_uri(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _stats_from_lengths(lengths: list[int], total_files: int, completed_files: int, failed_files: int) -> dict:
    if not lengths:
        return {
            "chunk_count": 0,
            "avg_char_count": 0,
            "min_char_count": 0,
            "max_char_count": 0,
            "completed_files": completed_files,
            "failed_files": failed_files,
            "total_files": total_files,
        }
    return {
        "chunk_count": len(lengths),
        "avg_char_count": round(sum(lengths) / len(lengths), 2),
        "min_char_count": min(lengths),
        "max_char_count": max(lengths),
        "completed_files": completed_files,
        "failed_files": failed_files,
        "total_files": total_files,
    }


async def _recompute_run_progress(session: AsyncSession, run_id: str, errors: list[str]) -> None:
    run = await get_chunk_run_model(session, run_id)
    completed = sum(1 for item in run.file_runs if item.status == "completed")
    failed = sum(1 for item in run.file_runs if item.status == "failed")
    total_chunks = sum(item.chunk_count for item in run.file_runs)
    lengths = (
        await session.scalars(select(Chunk.char_count).where(Chunk.run_id == run_id))
    ).all()
    run.completed_files = completed
    run.failed_files = failed
    run.total_chunks = total_chunks
    run.stats = _stats_from_lengths(list(lengths), run.total_files, completed, failed)
    run.error_summary = "\n".join(errors[-5:]) if errors else None
    await session.commit()


async def execute_chunk_run(run_id: str) -> None:
    async with AsyncSessionLocal() as session:
        run = await get_chunk_run_model(session, run_id)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await session.commit()

    errors: list[str] = []
    async with AsyncSessionLocal() as session:
        file_runs = (
            await session.scalars(
                select(ChunkFileRun)
                .where(ChunkFileRun.run_id == run_id)
                .options(
                    selectinload(ChunkFileRun.parsed_document)
                    .selectinload(ParsedDocument.file_run)
                    .selectinload(ParseFileRun.file)
                )
                .order_by(ChunkFileRun.created_at)
            )
        ).all()

    for file_run in file_runs:
        async with AsyncSessionLocal() as session:
            current = await session.scalar(
                select(ChunkFileRun)
                .where(ChunkFileRun.file_run_id == file_run.file_run_id)
                .options(
                    selectinload(ChunkFileRun.run),
                    selectinload(ChunkFileRun.parsed_document)
                    .selectinload(ParsedDocument.file_run)
                    .selectinload(ParseFileRun.file),
                )
            )
            if not current:
                continue
            current.status = "running"
            current.started_at = datetime.now(UTC)
            await session.commit()
            started = time.perf_counter()
            try:
                adapter = get_adapter(current.run.chunker_name)
                results = adapter.chunk(_document_input(current), current.run.chunker_config or {})
                artifact_dir = _artifact_root() / run_id
                artifact_dir.mkdir(parents=True, exist_ok=True)
                artifact_path = artifact_dir / f"{current.file_run_id}.json"
                payload = [result.__dict__ for result in results]
                artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                for result in results:
                    session.add(
                        Chunk(
                            run_id=run_id,
                            file_run_id=current.file_run_id,
                            parsed_document_id=current.parsed_document_id,
                            source_file_id=current.source_file_id,
                            chunk_index=result.chunk_index,
                            contents=result.contents,
                            source_text=result.source_text,
                            start_char=result.start_char,
                            end_char=result.end_char,
                            char_count=result.char_count,
                            token_count=result.token_count,
                            chunk_metadata=result.metadata,
                            source_element_refs=result.source_element_refs,
                            strategy_metadata=result.strategy_metadata,
                        )
                    )
                current.status = "completed"
                current.chunk_count = len(results)
                current.latency_ms = int((time.perf_counter() - started) * 1000)
                current.error = None
                current.artifact_uri = _relative_uri(artifact_path)
                current.ended_at = datetime.now(UTC)
            except Exception as exc:
                current.status = "failed"
                current.latency_ms = int((time.perf_counter() - started) * 1000)
                current.error = str(exc)
                current.ended_at = datetime.now(UTC)
                file_name = current.parsed_document.file_run.file.original_filename if current.parsed_document.file_run and current.parsed_document.file_run.file else current.source_file_id
                errors.append(f"{file_name}: {exc}")
            await session.commit()
        async with AsyncSessionLocal() as session:
            await _recompute_run_progress(session, run_id, errors)

    async with AsyncSessionLocal() as session:
        run = await get_chunk_run_model(session, run_id)
        if run.failed_files == run.total_files:
            run.status = "failed"
        elif run.failed_files:
            run.status = "completed_with_errors"
        else:
            run.status = "completed"
        run.ended_at = datetime.now(UTC)
        artifact_path = _artifact_root() / run_id / "_run_summary.json"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(
            json.dumps(
                {
                    "run_id": run.run_id,
                    "batch_id": run.batch_id,
                    "parse_run_id": run.parse_run_id,
                    "chunker_name": run.chunker_name,
                    "chunker_config": run.chunker_config,
                    "stats": run.stats,
                    "status": run.status,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        run.artifact_uri = _relative_uri(artifact_path)
        await session.commit()


async def list_chunk_file_runs(session: AsyncSession, run_id: str) -> list[ChunkFileRunOut]:
    await get_chunk_run_model(session, run_id)
    rows = (
        await session.scalars(
            select(ChunkFileRun)
            .where(ChunkFileRun.run_id == run_id)
            .options(
                selectinload(ChunkFileRun.parsed_document)
                .selectinload(ParsedDocument.file_run)
                .selectinload(ParseFileRun.file)
            )
            .order_by(ChunkFileRun.created_at)
        )
    ).all()
    return [chunk_file_run_out(row) for row in rows]


async def get_chunk_file_run(
    session: AsyncSession, run_id: str, file_run_id: str
) -> ChunkFileRunOut:
    row = await session.scalar(
        select(ChunkFileRun)
        .where(ChunkFileRun.run_id == run_id, ChunkFileRun.file_run_id == file_run_id)
        .options(
            selectinload(ChunkFileRun.parsed_document)
            .selectinload(ParsedDocument.file_run)
            .selectinload(ParseFileRun.file)
        )
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk file run not found")
    return chunk_file_run_out(row)


async def get_chunk_file_run_chunks(
    session: AsyncSession, run_id: str, file_run_id: str, offset: int = 0, limit: int = 50
) -> ChunkPageOut:
    await get_chunk_file_run(session, run_id, file_run_id)
    normalized_offset = max(offset, 0)
    normalized_limit = min(max(limit, 1), 500)
    total = await session.scalar(
        select(func.count()).select_from(Chunk).where(Chunk.run_id == run_id, Chunk.file_run_id == file_run_id)
    )
    rows = (
        await session.scalars(
            select(Chunk)
            .where(Chunk.run_id == run_id, Chunk.file_run_id == file_run_id)
            .order_by(Chunk.chunk_index)
            .offset(normalized_offset)
            .limit(normalized_limit)
        )
    ).all()
    return ChunkPageOut(
        items=[ChunkOut.model_validate(row, from_attributes=True) for row in rows],
        total=total or 0,
        offset=normalized_offset,
        limit=normalized_limit,
    )


async def compare_batch_chunk_runs(session: AsyncSession, batch_id: str) -> list[ChunkRunCompareOut]:
    batch = await material_service.get_batch(session, batch_id)
    runs = (
        await session.scalars(
            select(ChunkRun)
            .where(ChunkRun.batch_id == batch_id)
            .order_by(ChunkRun.created_at.desc())
        )
    ).all()
    return [
        ChunkRunCompareOut(
            run_id=run.run_id,
            batch_id=run.batch_id,
            batch_name=batch.batch_name,
            parse_run_id=run.parse_run_id,
            chunker_name=run.chunker_name,
            status=run.status,
            total_files=run.total_files,
            completed_files=run.completed_files,
            failed_files=run.failed_files,
            total_chunks=run.total_chunks,
            stats=run.stats,
            chunker_config=run.chunker_config,
            started_at=run.started_at,
            ended_at=run.ended_at,
            created_at=run.created_at,
        )
        for run in runs
    ]
