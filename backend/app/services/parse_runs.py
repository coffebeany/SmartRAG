from __future__ import annotations

import json
import shutil
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.models.entities import MaterialFile, ParseFileRun, ParsedDocument, ParseRun
from app.models.entities import ProcessingDefaultRule
from app.parsers.adapters import calculate_quality, get_adapter
from app.parsers.registry import parser_registry
from app.schemas.materials import (
    MaterialBatchOut,
    MaterialFileOut,
    ParseElementsPageOut,
    ParseFileRunDetailOut,
    ParseFileRunOut,
    ParseFileSelection,
    ParsePlanFileOut,
    ParsePlanOut,
    ParseRunCreate,
    ParseRunOut,
    ParsedDocumentOut,
    ParserStrategyOut,
)
from app.services import materials as material_service


def parser_strategy_out(strategy) -> ParserStrategyOut:
    availability = strategy.availability()
    return ParserStrategyOut(
        parser_name=strategy.parser_name,
        display_name=strategy.display_name,
        description=strategy.description,
        supported_file_exts=list(strategy.supported_file_exts),
        capabilities=list(strategy.capabilities),
        config_schema=strategy.config_schema,
        default_config=strategy.default_config,
        source=strategy.source,
        enabled=strategy.enabled,
        loaded_at=strategy.loaded_at,
        availability_status=availability.status,
        availability_reason=availability.reason,
        required_dependencies=list(strategy.required_dependencies),
        required_env_vars=list(strategy.required_env_vars),
        requires_config=strategy.requires_config,
        autorag_module_type=strategy.autorag_module_type,
        autorag_parse_method=strategy.autorag_parse_method,
    )


def parse_run_out(run: ParseRun) -> ParseRunOut:
    return ParseRunOut.model_validate(run, from_attributes=True).model_copy(
        update={"batch_name": run.batch.batch_name if run.batch else None}
    )


def parse_file_run_out(file_run: ParseFileRun) -> ParseFileRunOut:
    return ParseFileRunOut.model_validate(file_run, from_attributes=True).model_copy(
        update={
            "original_filename": file_run.file.original_filename if file_run.file else None,
            "file_ext": file_run.file.file_ext if file_run.file else None,
        }
    )


async def list_parser_strategies() -> list[ParserStrategyOut]:
    return [parser_strategy_out(strategy) for strategy in parser_registry.list_enabled()]


def _parser_config_from_rule(rule: ProcessingDefaultRule | None, strategy) -> dict:
    if rule and rule.parser_config_yaml:
        try:
            parsed = json.loads(rule.parser_config_yaml)
        except json.JSONDecodeError:
            parsed = {}
        if isinstance(parsed, dict):
            return strategy.default_config | parsed
    return dict(strategy.default_config)


async def get_parse_plan(session: AsyncSession, batch_id: str) -> ParsePlanOut:
    batch = await material_service.get_batch(session, batch_id)
    await material_service._ensure_processing_rules(session)
    rules = {
        rule.file_ext: rule
        for rule in await session.scalars(select(ProcessingDefaultRule))
    }
    active_files = [
        file for file in sorted(batch.files, key=lambda item: item.original_filename)
        if file.status == "active"
    ]
    files: list[ParsePlanFileOut] = []
    for file in active_files:
        options = [parser_strategy_out(strategy) for strategy in parser_registry.parsers_for_extension(file.file_ext)]
        rule = rules.get(file.file_ext)
        default_strategy = parser_registry.default_parser_for_extension(file.file_ext)
        default_parser_name = rule.parser_name if rule and rule.enabled else (
            default_strategy.parser_name if default_strategy else None
        )
        selected_default_strategy = parser_registry.get(default_parser_name) if default_parser_name else None
        files.append(
            ParsePlanFileOut(
                file=MaterialFileOut.model_validate(file, from_attributes=True),
                default_parser_name=default_parser_name,
                default_parser_config=_parser_config_from_rule(rule, selected_default_strategy)
                if selected_default_strategy
                else {},
                parser_options=options,
            )
        )
    return ParsePlanOut(
        batch=MaterialBatchOut.model_validate(batch, from_attributes=True),
        files=files,
    )


def _validate_selection(file: MaterialFile, selection: ParseFileSelection) -> None:
    if file.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"File {file.file_id} is not active")
    strategy = parser_registry.get(selection.parser_name)
    if not strategy:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown parser: {selection.parser_name}")
    if file.file_ext not in strategy.supported_file_exts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parser {selection.parser_name} does not support {file.file_ext}",
        )
    availability = strategy.availability()
    if availability.status not in {"available", "needs_config"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parser {selection.parser_name} is not executable: {availability.reason}",
        )
    required = strategy.config_schema.get("required", [])
    missing = [key for key in required if selection.parser_config.get(key) in (None, "")]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Parser {selection.parser_name} missing config: {', '.join(missing)}",
        )


async def create_parse_run(session: AsyncSession, payload: ParseRunCreate) -> ParseRunOut:
    batch = await material_service.get_batch(session, payload.batch_id)
    active_files = {file.file_id: file for file in batch.files if file.status == "active"}
    if not payload.files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files selected")

    for selection in payload.files:
        file = active_files.get(selection.file_id)
        if not file:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown active file: {selection.file_id}")
        _validate_selection(file, selection)

    run = ParseRun(
        batch_id=batch.batch_id,
        batch_version_id=batch.current_version_id,
        status="pending",
        total_files=len(payload.files),
    )
    session.add(run)
    await session.flush()
    for selection in payload.files:
        session.add(
            ParseFileRun(
                run_id=run.run_id,
                file_id=selection.file_id,
                parser_name=selection.parser_name,
                parser_config=selection.parser_config,
            )
        )
    await session.commit()
    refreshed = await get_parse_run_model(session, run.run_id)
    return parse_run_out(refreshed)


async def get_parse_run_model(session: AsyncSession, run_id: str) -> ParseRun:
    run = await session.scalar(
        select(ParseRun)
        .where(ParseRun.run_id == run_id)
        .options(selectinload(ParseRun.batch), selectinload(ParseRun.file_runs).selectinload(ParseFileRun.file))
    )
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parse run not found")
    return run


async def list_parse_runs(session: AsyncSession) -> list[ParseRunOut]:
    runs = (
        await session.scalars(
            select(ParseRun)
            .options(selectinload(ParseRun.batch))
            .order_by(ParseRun.created_at.desc())
        )
    ).all()
    return [parse_run_out(run) for run in runs]


async def get_parse_run(session: AsyncSession, run_id: str) -> ParseRunOut:
    return parse_run_out(await get_parse_run_model(session, run_id))


async def delete_parse_run(session: AsyncSession, run_id: str) -> None:
    run = await get_parse_run_model(session, run_id)
    await session.delete(run)
    await session.commit()
    artifact_dir = _artifact_root() / run_id
    root = _artifact_root().resolve()
    resolved_artifact_dir = artifact_dir.resolve()
    if resolved_artifact_dir.exists() and resolved_artifact_dir.is_dir():
        try:
            resolved_artifact_dir.relative_to(root)
        except ValueError as exc:
            raise RuntimeError("Parse artifact path escaped artifact root") from exc
        shutil.rmtree(resolved_artifact_dir)


async def list_parse_file_runs(session: AsyncSession, run_id: str) -> list[ParseFileRunOut]:
    await get_parse_run_model(session, run_id)
    rows = (
        await session.scalars(
            select(ParseFileRun)
            .where(ParseFileRun.run_id == run_id)
            .options(selectinload(ParseFileRun.file))
            .order_by(ParseFileRun.created_at)
        )
    ).all()
    return [parse_file_run_out(row) for row in rows]


async def get_parse_file_run_detail(
    session: AsyncSession, run_id: str, file_run_id: str
) -> ParseFileRunDetailOut:
    file_run = await session.scalar(
        select(ParseFileRun)
        .where(ParseFileRun.run_id == run_id, ParseFileRun.file_run_id == file_run_id)
        .options(selectinload(ParseFileRun.file), selectinload(ParseFileRun.parsed_document))
    )
    if not file_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parse file run not found")
    parsed = file_run.parsed_document
    return ParseFileRunDetailOut(
        file_run=parse_file_run_out(file_run),
        parsed_document=ParsedDocumentOut.model_validate(parsed, from_attributes=True) if parsed else None,
    )


def _paginate_elements(
    elements: list[dict], offset: int = 0, limit: int = 50
) -> ParseElementsPageOut:
    normalized_offset = max(offset, 0)
    normalized_limit = min(max(limit, 1), 500)
    return ParseElementsPageOut(
        items=elements[normalized_offset : normalized_offset + normalized_limit],
        total=len(elements),
        offset=normalized_offset,
        limit=normalized_limit,
    )


async def get_parse_file_run_elements(
    session: AsyncSession, run_id: str, file_run_id: str, offset: int = 0, limit: int = 50
) -> ParseElementsPageOut:
    file_run = await session.scalar(
        select(ParseFileRun)
        .where(ParseFileRun.run_id == run_id, ParseFileRun.file_run_id == file_run_id)
        .options(selectinload(ParseFileRun.parsed_document))
    )
    if not file_run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parse file run not found")
    parsed = file_run.parsed_document
    elements = parsed.elements if parsed else []
    return _paginate_elements(elements, offset, limit)


def _artifact_root() -> Path:
    root = Path(settings.parse_artifact_root)
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


async def execute_parse_run(run_id: str) -> None:
    async with AsyncSessionLocal() as session:
        run = await get_parse_run_model(session, run_id)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await session.commit()

    async with AsyncSessionLocal() as session:
        file_runs = (
            await session.scalars(
                select(ParseFileRun)
                .where(ParseFileRun.run_id == run_id)
                .options(selectinload(ParseFileRun.file))
                .order_by(ParseFileRun.created_at)
            )
        ).all()

    errors: list[str] = []
    for file_run in file_runs:
        async with AsyncSessionLocal() as session:
            current = await session.scalar(
                select(ParseFileRun)
                .where(ParseFileRun.file_run_id == file_run.file_run_id)
                .options(selectinload(ParseFileRun.file))
            )
            if not current:
                continue
            current.status = "running"
            current.started_at = datetime.now(UTC)
            await session.commit()

            started = time.perf_counter()
            try:
                adapter = get_adapter(current.parser_name)
                path = material_service.resolve_storage_path(current.file.storage_uri)
                result = adapter.parse(path, current.parser_config or {})
                latency_ms = int((time.perf_counter() - started) * 1000)
                quality = calculate_quality(result)
                artifact_dir = _artifact_root() / run_id
                artifact_dir.mkdir(parents=True, exist_ok=True)
                artifact_path = artifact_dir / f"{current.file_run_id}.json"
                payload = {
                    "text_content": result.text,
                    "elements": result.elements,
                    "metadata": result.metadata,
                    "pages": result.pages,
                    "char_count": len(result.text),
                }
                artifact_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
                try:
                    artifact_uri = str(artifact_path.relative_to(Path.cwd())).replace("\\", "/")
                except ValueError:
                    artifact_uri = str(artifact_path).replace("\\", "/")
                document = ParsedDocument(
                    run_id=run_id,
                    file_run_id=current.file_run_id,
                    file_id=current.file_id,
                    parser_name=current.parser_name,
                    text_content=result.text,
                    elements=result.elements,
                    document_metadata=result.metadata,
                    pages=result.pages,
                    char_count=len(result.text),
                    artifact_uri=artifact_uri,
                )
                current.status = "completed"
                current.latency_ms = latency_ms
                current.quality_score = quality
                current.error = None
                current.output_artifact_uri = artifact_uri
                current.ended_at = datetime.now(UTC)
                session.add(document)
            except Exception as exc:
                latency_ms = int((time.perf_counter() - started) * 1000)
                current.status = "failed"
                current.latency_ms = latency_ms
                current.error = str(exc)
                current.ended_at = datetime.now(UTC)
                errors.append(f"{current.file.original_filename}: {exc}")
            await session.commit()

        async with AsyncSessionLocal() as session:
            run = await get_parse_run_model(session, run_id)
            completed = sum(1 for item in run.file_runs if item.status == "completed")
            failed = sum(1 for item in run.file_runs if item.status == "failed")
            run.completed_files = completed
            run.failed_files = failed
            run.error_summary = "\n".join(errors[-5:]) if errors else None
            await session.commit()

    async with AsyncSessionLocal() as session:
        run = await get_parse_run_model(session, run_id)
        if run.failed_files == run.total_files:
            run.status = "failed"
        elif run.failed_files:
            run.status = "completed_with_errors"
        else:
            run.status = "completed"
        run.ended_at = datetime.now(UTC)
        await session.commit()
