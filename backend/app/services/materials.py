from __future__ import annotations

import hashlib
import importlib
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.chunkers import chunker_registry
from app.core.config import settings
from app.models.entities import (
    MaterialBatch,
    MaterialBatchVersion,
    MaterialFile,
    ProcessingDefaultRule,
)
from app.parsers import parser_registry
from app.schemas.materials import (
    MaterialBatchCreate,
    MaterialBatchOut,
    MaterialBatchUpdate,
    MaterialBatchVersionOut,
    MaterialFileOut,
    ParserStrategyOut,
    ProcessingDefaultRuleOut,
    ProcessingDefaultRulesUpdate,
    UploadFilesOut,
)


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "uploaded_file"
    name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "_", name)
    return name[:180] or "uploaded_file"


def file_ext(filename: str) -> str:
    return Path(filename).suffix.lower()


def supported_file_exts() -> list[str]:
    return parser_registry.supported_extensions()


def resolve_storage_path(storage_uri: str) -> Path:
    path = Path(storage_uri)
    if path.is_absolute():
        return path
    return Path.cwd() / path


def active_snapshot(files: list[MaterialFile]) -> list[str]:
    return sorted(file.file_id for file in files if file.status == "active")


async def get_batch(session: AsyncSession, batch_id: str) -> MaterialBatch:
    batch = await session.scalar(
        select(MaterialBatch)
        .where(MaterialBatch.batch_id == batch_id)
        .options(selectinload(MaterialBatch.files), selectinload(MaterialBatch.versions))
    )
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material batch not found")
    return batch


async def list_batches(session: AsyncSession) -> list[MaterialBatchOut]:
    batches = (
        await session.scalars(select(MaterialBatch).order_by(MaterialBatch.updated_at.desc()))
    ).all()
    return [MaterialBatchOut.model_validate(batch, from_attributes=True) for batch in batches]


async def create_batch(session: AsyncSession, payload: MaterialBatchCreate) -> MaterialBatchOut:
    batch = MaterialBatch(**payload.model_dump(), current_version=1, file_count=0)
    session.add(batch)
    await session.flush()
    version = MaterialBatchVersion(
        batch_id=batch.batch_id,
        version_number=1,
        parent_version_id=None,
        change_type="batch_created",
        added_file_ids=[],
        removed_file_ids=[],
        active_file_ids_snapshot=[],
        manifest_uri=None,
        created_by=payload.created_by,
    )
    session.add(version)
    await session.flush()
    batch.current_version_id = version.batch_version_id
    await session.commit()
    await session.refresh(batch)
    return MaterialBatchOut.model_validate(batch, from_attributes=True)


async def update_batch(
    session: AsyncSession, batch_id: str, payload: MaterialBatchUpdate
) -> MaterialBatchOut:
    batch = await get_batch(session, batch_id)
    updates = payload.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(batch, key, value)
    await session.commit()
    await session.refresh(batch)
    return MaterialBatchOut.model_validate(batch, from_attributes=True)


async def delete_batch(session: AsyncSession, batch_id: str) -> None:
    batch = await get_batch(session, batch_id)
    storage_uris = sorted({file.storage_uri for file in batch.files if file.storage_uri})
    deletable_paths: list[Path] = []
    for storage_uri in storage_uris:
        reference_count = await session.scalar(
            select(MaterialFile.file_id).where(
                MaterialFile.storage_uri == storage_uri,
                MaterialFile.batch_id != batch_id,
            ).limit(1)
        )
        if reference_count is None:
            deletable_paths.append(resolve_storage_path(storage_uri))

    batch_storage_dir: Path | None = None
    storage_root = Path(settings.material_storage_root)
    if not storage_root.is_absolute():
        storage_root = Path.cwd() / storage_root
    candidate_dir = storage_root / batch.batch_id
    if candidate_dir.exists():
        batch_storage_dir = candidate_dir

    await session.delete(batch)
    await session.commit()

    for path in deletable_paths:
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            continue
    if batch_storage_dir:
        try:
            batch_storage_dir.rmdir()
        except OSError:
            pass


async def list_files(session: AsyncSession, batch_id: str) -> list[MaterialFileOut]:
    await get_batch(session, batch_id)
    files = (
        await session.scalars(
            select(MaterialFile)
            .where(MaterialFile.batch_id == batch_id)
            .order_by(MaterialFile.created_at.desc())
        )
    ).all()
    return [MaterialFileOut.model_validate(file, from_attributes=True) for file in files]


async def list_versions(session: AsyncSession, batch_id: str) -> list[MaterialBatchVersionOut]:
    await get_batch(session, batch_id)
    versions = (
        await session.scalars(
            select(MaterialBatchVersion)
            .where(MaterialBatchVersion.batch_id == batch_id)
            .order_by(MaterialBatchVersion.version_number.desc())
        )
    ).all()
    return [MaterialBatchVersionOut.model_validate(version, from_attributes=True) for version in versions]


async def _create_version(
    session: AsyncSession,
    batch: MaterialBatch,
    *,
    change_type: str,
    added_file_ids: list[str] | None = None,
    removed_file_ids: list[str] | None = None,
    created_by: str | None = None,
) -> MaterialBatchVersion:
    await session.flush()
    active_ids = sorted(
        (
            await session.scalars(
                select(MaterialFile.file_id).where(
                    MaterialFile.batch_id == batch.batch_id,
                    MaterialFile.status == "active",
                )
            )
        ).all()
    )
    version = MaterialBatchVersion(
        batch_id=batch.batch_id,
        version_number=batch.current_version + 1,
        parent_version_id=batch.current_version_id,
        change_type=change_type,
        added_file_ids=added_file_ids or [],
        removed_file_ids=removed_file_ids or [],
        active_file_ids_snapshot=active_ids,
        manifest_uri=None,
        created_by=created_by,
    )
    session.add(version)
    await session.flush()
    batch.current_version = version.version_number
    batch.current_version_id = version.batch_version_id
    batch.file_count = len(active_ids)
    return version


async def upload_files(
    session: AsyncSession, batch_id: str, uploads: list[UploadFile], created_by: str | None = None
) -> UploadFilesOut:
    batch = await get_batch(session, batch_id)
    if not uploads:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files uploaded")
    unsupported = sorted(
        {
            file_ext(upload.filename or "")
            for upload in uploads
            if not parser_registry.supports_extension(file_ext(upload.filename or ""))
        }
    )
    if unsupported:
        supported = ", ".join(supported_file_exts())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"包含不支持的文件类型：{', '.join(unsupported)}。当前支持：{supported}",
        )

    storage_root = Path(settings.material_storage_root)
    if not storage_root.is_absolute():
        storage_root = Path.cwd() / storage_root
    batch_dir = storage_root / batch.batch_id
    batch_dir.mkdir(parents=True, exist_ok=True)

    existing_checksums = {
        row[0]
        for row in (
            await session.execute(select(MaterialFile.checksum).where(MaterialFile.batch_id == batch_id))
        ).all()
    }
    created_files: list[MaterialFile] = []
    duplicate_checksums: list[str] = []

    for upload in uploads:
        content = await upload.read()
        checksum = hashlib.sha256(content).hexdigest()
        if checksum in existing_checksums:
            duplicate_checksums.append(checksum)
        name = safe_filename(upload.filename or "uploaded_file")
        material_file = MaterialFile(
            batch_id=batch.batch_id,
            original_filename=name,
            file_ext=file_ext(name),
            mime_type=upload.content_type,
            size_bytes=len(content),
            checksum=checksum,
            storage_uri="",
            status="active",
        )
        session.add(material_file)
        await session.flush()
        target = batch_dir / f"{material_file.file_id}_{name}"
        target.write_bytes(content)
        try:
            material_file.storage_uri = str(target.relative_to(Path.cwd())).replace("\\", "/")
        except ValueError:
            material_file.storage_uri = str(target).replace("\\", "/")
        created_files.append(material_file)
        existing_checksums.add(checksum)

    version = await _create_version(
        session,
        batch,
        change_type="add_files",
        added_file_ids=[file.file_id for file in created_files],
        created_by=created_by,
    )
    await session.commit()
    refreshed = await get_batch(session, batch_id)
    return UploadFilesOut(
        batch=MaterialBatchOut.model_validate(refreshed, from_attributes=True),
        files=[MaterialFileOut.model_validate(file, from_attributes=True) for file in created_files],
        version=MaterialBatchVersionOut.model_validate(version, from_attributes=True),
        duplicate_checksums=duplicate_checksums,
    )


async def remove_file(
    session: AsyncSession, batch_id: str, file_id: str, created_by: str | None = None
) -> MaterialBatchVersionOut:
    batch = await get_batch(session, batch_id)
    material_file = next((file for file in batch.files if file.file_id == file_id), None)
    if not material_file:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Material file not found")
    if material_file.status == "removed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Material file already removed")
    material_file.status = "removed"
    material_file.removed_at = datetime.now(UTC)
    version = await _create_version(
        session,
        batch,
        change_type="remove_files",
        removed_file_ids=[file_id],
        created_by=created_by,
    )
    await session.commit()
    return MaterialBatchVersionOut.model_validate(version, from_attributes=True)


async def list_parser_strategies(session: AsyncSession) -> list[ParserStrategyOut]:
    return [
        ParserStrategyOut(
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
            availability_status=strategy.availability().status,
            availability_reason=strategy.availability().reason,
            required_dependencies=list(strategy.required_dependencies),
            required_env_vars=list(strategy.required_env_vars),
            requires_config=strategy.requires_config,
            autorag_module_type=strategy.autorag_module_type,
            autorag_parse_method=strategy.autorag_parse_method,
        )
        for strategy in parser_registry.list_enabled()
    ]


async def refresh_parser_strategies(session: AsyncSession) -> list[ParserStrategyOut]:
    importlib.invalidate_caches()
    return await list_parser_strategies(session)


async def _ensure_processing_rules(session: AsyncSession) -> None:
    existing_rules = {
        rule.file_ext: rule
        for rule in (
            await session.scalars(
                select(ProcessingDefaultRule).where(ProcessingDefaultRule.project_id.is_(None))
            )
        ).all()
    }
    for ext in supported_file_exts():
        default_parser = parser_registry.default_parser_for_extension(ext)
        if not default_parser:
            continue
        if ext in existing_rules:
            existing = existing_rules[ext]
            if not parser_registry.has_parser_for_extension(existing.parser_name, ext):
                existing.parser_name = default_parser.parser_name
                existing.parser_config_yaml = None
            continue
        session.add(
            ProcessingDefaultRule(
                file_ext=ext,
                parser_name=default_parser.parser_name,
                parser_config_yaml=None,
                chunker_plugin_id="llama_index_sentence",
                metadata_strategy_id="metadata.basic",
                enabled=True,
            )
        )
    await session.flush()


async def list_processing_rules(session: AsyncSession) -> list[ProcessingDefaultRuleOut]:
    await _ensure_processing_rules(session)
    await session.commit()
    rows = (
        await session.scalars(
            select(ProcessingDefaultRule).order_by(ProcessingDefaultRule.file_ext)
        )
    ).all()
    return [ProcessingDefaultRuleOut.model_validate(row, from_attributes=True) for row in rows]


async def update_processing_rules(
    session: AsyncSession, payload: ProcessingDefaultRulesUpdate
) -> list[ProcessingDefaultRuleOut]:
    for incoming in payload.rules:
        normalized_ext = incoming.file_ext.lower()
        if not parser_registry.supports_extension(normalized_ext):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file extension: {normalized_ext}",
            )
        if not parser_registry.has_parser_for_extension(incoming.parser_name, normalized_ext):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Parser {incoming.parser_name} does not support {normalized_ext}",
            )
        if incoming.chunker_plugin_id and not chunker_registry.get(incoming.chunker_plugin_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unknown chunker: {incoming.chunker_plugin_id}",
            )
        existing = None
        if incoming.rule_id:
            existing = await session.get(ProcessingDefaultRule, incoming.rule_id)
        if not existing:
            project_filter = (
                ProcessingDefaultRule.project_id.is_(None)
                if incoming.project_id is None
                else ProcessingDefaultRule.project_id == incoming.project_id
            )
            existing = await session.scalar(
                select(ProcessingDefaultRule).where(
                    project_filter,
                    ProcessingDefaultRule.file_ext == normalized_ext,
                )
            )
        values = incoming.model_dump(exclude={"rule_id"})
        values["file_ext"] = normalized_ext
        values["embedding_text_template_id"] = None
        values["priority"] = 100
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            session.add(ProcessingDefaultRule(**values))
    await session.commit()
    return await list_processing_rules(session)
