from __future__ import annotations

import random
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.evaluators.adapters import get_evaluation_adapter
from app.evaluators.registry import (
    EvaluationFrameworkSpec,
    ParseEvaluatorSpec,
    evaluation_framework_registry,
    parse_evaluator_registry,
)
from app.models.entities import (
    Chunk,
    ChunkRun,
    EvaluationDatasetItem,
    EvaluationDatasetRun,
    EvaluationReportItem,
    EvaluationReportRun,
    ModelDefault,
    ModelConnection,
    RagFlow,
    RagFlowRun,
    VectorRun,
)
from app.schemas.evaluations import (
    EvaluationDatasetItemOut,
    EvaluationDatasetItemsPageOut,
    EvaluationDatasetRunCreate,
    EvaluationDatasetRunOut,
    EvaluationFrameworkOut,
    EvaluationMetricOut,
    EvaluationReportItemOut,
    EvaluationReportItemsPageOut,
    EvaluationReportRunCreate,
    EvaluationReportRunOut,
    ParseEvaluationRunCreate,
    ParseEvaluatorOut,
)
from app.schemas.rag import RagFlowRunCreate
from app.services import rag as rag_service


def parse_evaluator_out(evaluator: ParseEvaluatorSpec) -> ParseEvaluatorOut:
    availability = evaluator.availability()
    return ParseEvaluatorOut(
        evaluator_name=evaluator.evaluator_name,
        display_name=evaluator.display_name,
        description=evaluator.description,
        capabilities=list(evaluator.capabilities),
        config_schema=evaluator.config_schema,
        default_config=evaluator.default_config,
        source=evaluator.source,
        enabled=evaluator.enabled,
        availability_status=availability.status,
        availability_reason=availability.reason,
    )


async def list_parse_evaluators() -> list[ParseEvaluatorOut]:
    return [
        parse_evaluator_out(evaluator)
        for evaluator in parse_evaluator_registry.list_enabled()
    ]


async def create_parse_evaluation_run(payload: ParseEvaluationRunCreate) -> None:
    evaluator = parse_evaluator_registry.get(payload.evaluator_name)
    if not evaluator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown parse evaluator: {payload.evaluator_name}",
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Parse quality evaluation execution is not connected yet.",
    )


def _framework_out(framework: EvaluationFrameworkSpec) -> EvaluationFrameworkOut:
    availability = framework.availability()
    install_hint = f"uv sync --extra {framework.optional_dependency_extra}" if framework.optional_dependency_extra else None
    return EvaluationFrameworkOut(
        framework_id=framework.framework_id,
        display_name=framework.display_name,
        description=framework.description,
        source=framework.source,
        default_metrics=list(framework.default_metrics),
        metrics=[EvaluationMetricOut(**metric.__dict__) for metric in framework.metrics],
        generator_config_schema=framework.generator_config_schema,
        default_generator_config=framework.default_generator_config,
        availability_status=availability.status,
        availability_reason=availability.reason,
        dependency_install_hint=install_hint,
    )


async def list_evaluation_frameworks() -> list[EvaluationFrameworkOut]:
    return [_framework_out(framework) for framework in evaluation_framework_registry.list()]


def _known_framework(framework_id: str) -> EvaluationFrameworkSpec:
    framework = evaluation_framework_registry.get(framework_id)
    if not framework:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown evaluation framework: {framework_id}")
    return framework


def _merge_generator_config(framework: EvaluationFrameworkSpec, config: dict[str, Any]) -> dict[str, Any]:
    defaults = dict(framework.default_generator_config)
    advanced = config.get("advanced_config") if isinstance(config.get("advanced_config"), dict) else {}
    merged = defaults | {key: value for key, value in config.items() if value not in (None, "")}
    if isinstance(defaults.get("query_distribution"), dict) and isinstance(config.get("query_distribution"), dict):
        merged["query_distribution"] = defaults["query_distribution"] | config["query_distribution"]
    if isinstance(defaults.get("chunk_sampling"), dict) and isinstance(config.get("chunk_sampling"), dict):
        merged["chunk_sampling"] = defaults["chunk_sampling"] | config["chunk_sampling"]
    merged["advanced_config"] = advanced
    return merged


def _dataset_run_out(row: EvaluationDatasetRun) -> EvaluationDatasetRunOut:
    return EvaluationDatasetRunOut.model_validate(row, from_attributes=True).model_copy(
        update={
            "batch_name": row.batch.batch_name if row.batch else None,
            "chunk_status": row.chunk_run.status if row.chunk_run else None,
        }
    )


def _report_run_out(row: EvaluationReportRun) -> EvaluationReportRunOut:
    return EvaluationReportRunOut.model_validate(row, from_attributes=True).model_copy(
        update={
            "flow_name": row.flow.flow_name if row.flow else None,
            "dataset_status": row.dataset_run.status if row.dataset_run else None,
        }
    )


async def _get_model(session: AsyncSession, model_id: str | None) -> ModelConnection | None:
    if not model_id:
        return None
    model = await session.get(ModelConnection, model_id)
    if not model or not model.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Model is unavailable")
    return model


async def _get_default_model_id(session: AsyncSession, default_key: str) -> str | None:
    default = await session.get(ModelDefault, default_key)
    return default.model_id if default else None


async def _resolve_model_id(
    session: AsyncSession,
    model_id: str | None,
    *,
    default_key: str,
    required_label: str,
) -> str:
    resolved_id = model_id or await _get_default_model_id(session, default_key)
    if not resolved_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{required_label} is required. Configure {default_key} in Settings > Model Defaults or select a model explicitly.",
        )
    model = await _get_model(session, resolved_id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{required_label} is required. Configure {default_key} in Settings > Model Defaults or select a model explicitly.",
        )
    return model.model_id


async def _resolve_embedding_model(session: AsyncSession, model_id: str | None) -> ModelConnection:
    resolved_id = await _resolve_model_id(
        session,
        model_id,
        default_key="default_embedding_model",
        required_label="embedding_model_id",
    )
    model = await _get_model(session, resolved_id)
    if not model:
        raise RuntimeError("default_embedding_model is unavailable")
    if model.model_category != "embedding":
        source = "embedding_model_id" if model_id else "default_embedding_model"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{source} must point to an enabled embedding model.",
        )
    return model


async def create_evaluation_dataset_run(session: AsyncSession, payload: EvaluationDatasetRunCreate) -> EvaluationDatasetRunOut:
    framework = _known_framework(payload.framework_id)
    availability = framework.availability()
    if availability.status != "available":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=availability.reason)
    chunk_run = await session.get(ChunkRun, payload.chunk_run_id)
    if not chunk_run or chunk_run.batch_id != payload.batch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Chunk run not found in batch")
    if chunk_run.status not in {"completed", "completed_with_errors"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Chunk run is not completed")
    await _get_model(session, payload.judge_llm_model_id)
    embedding = await _resolve_embedding_model(session, payload.embedding_model_id)
    generator_config = _merge_generator_config(framework, payload.generator_config)
    run = EvaluationDatasetRun(
        batch_id=payload.batch_id,
        chunk_run_id=payload.chunk_run_id,
        framework_id=payload.framework_id,
        generator_config=generator_config,
        judge_llm_model_id=payload.judge_llm_model_id,
        embedding_model_id=embedding.model_id,
        total_items=int(generator_config.get("testset_size") or 10),
        stats={"requested_items": int(generator_config.get("testset_size") or 10)},
    )
    session.add(run)
    await session.commit()
    refreshed = await get_evaluation_dataset_run_model(session, run.run_id)
    return _dataset_run_out(refreshed)


async def get_evaluation_dataset_run_model(session: AsyncSession, run_id: str) -> EvaluationDatasetRun:
    row = await session.scalar(
        select(EvaluationDatasetRun)
        .where(EvaluationDatasetRun.run_id == run_id)
        .options(selectinload(EvaluationDatasetRun.batch), selectinload(EvaluationDatasetRun.chunk_run))
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation dataset run not found")
    return row


async def list_evaluation_dataset_runs(session: AsyncSession) -> list[EvaluationDatasetRunOut]:
    rows = (
        await session.scalars(
            select(EvaluationDatasetRun)
            .options(selectinload(EvaluationDatasetRun.batch), selectinload(EvaluationDatasetRun.chunk_run))
            .order_by(EvaluationDatasetRun.created_at.desc())
        )
    ).all()
    return [_dataset_run_out(row) for row in rows]


async def get_evaluation_dataset_run(session: AsyncSession, run_id: str) -> EvaluationDatasetRunOut:
    return _dataset_run_out(await get_evaluation_dataset_run_model(session, run_id))


async def _delete_owned_rag_flow_runs(session: AsyncSession, run_ids: set[str]) -> None:
    if not run_ids:
        return
    rows = (await session.scalars(select(RagFlowRun).where(RagFlowRun.run_id.in_(run_ids)))).all()
    for row in rows:
        await session.delete(row)


async def delete_evaluation_dataset_run(session: AsyncSession, run_id: str) -> None:
    run = await get_evaluation_dataset_run_model(session, run_id)
    if run.status in {"pending", "running"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete a running evaluation dataset task")
    rag_run_ids = set(
        (
            await session.scalars(
                select(EvaluationReportItem.rag_flow_run_id)
                .join(EvaluationReportRun, EvaluationReportRun.run_id == EvaluationReportItem.run_id)
                .where(EvaluationReportRun.dataset_run_id == run_id, EvaluationReportItem.rag_flow_run_id.is_not(None))
            )
        ).all()
    )
    await session.delete(run)
    await session.flush()
    await _delete_owned_rag_flow_runs(session, {item for item in rag_run_ids if item})
    await session.commit()


def _sample_chunks(chunks: list[Chunk], config: dict[str, Any]) -> list[Chunk]:
    sampling = config.get("chunk_sampling") if isinstance(config.get("chunk_sampling"), dict) else {}
    min_chars = int(sampling.get("min_char_count") or 0)
    max_chars = int(sampling.get("max_char_count") or 0)
    file_ids = set(sampling.get("source_file_ids") or [])
    filtered = [
        chunk
        for chunk in chunks
        if chunk.char_count >= min_chars
        and (not max_chars or chunk.char_count <= max_chars)
        and (not file_ids or chunk.source_file_id in file_ids)
    ]
    seed = config.get("random_seed")
    if seed is not None:
        rng = random.Random(int(seed))
        rng.shuffle(filtered)
    max_chunks = int(sampling.get("max_chunks") or len(filtered) or 1)
    return filtered[:max_chunks]


async def execute_evaluation_dataset_run(run_id: str) -> None:
    async with AsyncSessionLocal() as session:
        run = await get_evaluation_dataset_run_model(session, run_id)
        run.status = "running"
        run.started_at = datetime.now(UTC)
        await session.commit()
    try:
        async with AsyncSessionLocal() as session:
            run = await get_evaluation_dataset_run_model(session, run_id)
            judge = await _get_model(session, run.judge_llm_model_id)
            if not judge:
                raise RuntimeError("judge_llm_model_id is required for dataset generation")
            embedding = await _resolve_embedding_model(session, run.embedding_model_id)
            if run.embedding_model_id != embedding.model_id:
                run.embedding_model_id = embedding.model_id
                await session.commit()
            chunks = (
                await session.scalars(
                    select(Chunk)
                    .where(Chunk.run_id == run.chunk_run_id)
                    .order_by(Chunk.source_file_id, Chunk.chunk_index)
                )
            ).all()
            selected_chunks = _sample_chunks(list(chunks), run.generator_config or {})
            adapter = get_evaluation_adapter(run.framework_id)
            samples = await adapter.generate_samples(
                chunks=selected_chunks,
                generator_config=run.generator_config or {},
                judge_llm_model=judge,
                embedding_model=embedding,
            )
            run.total_items = len(samples)
            for sample in samples:
                session.add(
                    EvaluationDatasetItem(
                        run_id=run.run_id,
                        question=sample.question,
                        ground_truth=sample.ground_truth,
                        reference_contexts=sample.reference_contexts,
                        source_chunk_ids=sample.source_chunk_ids,
                        source_file_ids=sample.source_file_ids,
                        synthesizer_name=sample.synthesizer_name,
                        item_metadata=sample.item_metadata,
                    )
                )
                run.completed_items += 1
            run.status = "completed"
            run.stats = {
                "requested_items": int((run.generator_config or {}).get("testset_size") or len(samples)),
                "generated_items": len(samples),
                "selected_chunks": len(selected_chunks),
            }
            run.ended_at = datetime.now(UTC)
            await session.commit()
    except Exception as exc:
        async with AsyncSessionLocal() as session:
            run = await get_evaluation_dataset_run_model(session, run_id)
            run.status = "failed"
            run.error_summary = str(exc)
            run.ended_at = datetime.now(UTC)
            await session.commit()


async def list_evaluation_dataset_items(
    session: AsyncSession, run_id: str, offset: int = 0, limit: int = 50
) -> EvaluationDatasetItemsPageOut:
    await get_evaluation_dataset_run_model(session, run_id)
    normalized_offset = max(offset, 0)
    normalized_limit = min(max(limit, 1), 500)
    total = await session.scalar(
        select(func.count()).select_from(EvaluationDatasetItem).where(EvaluationDatasetItem.run_id == run_id)
    )
    rows = (
        await session.scalars(
            select(EvaluationDatasetItem)
            .where(EvaluationDatasetItem.run_id == run_id)
            .order_by(EvaluationDatasetItem.created_at)
            .offset(normalized_offset)
            .limit(normalized_limit)
        )
    ).all()
    return EvaluationDatasetItemsPageOut(
        items=[EvaluationDatasetItemOut.model_validate(row, from_attributes=True) for row in rows],
        total=total or 0,
        offset=normalized_offset,
        limit=normalized_limit,
    )


def _flow_has_answer_generator(flow: RagFlow) -> bool:
    return any(node.get("enabled", True) and node.get("node_type") == "answer_generator" for node in flow.nodes or [])


async def create_evaluation_report_run(session: AsyncSession, payload: EvaluationReportRunCreate) -> EvaluationReportRunOut:
    framework = _known_framework(payload.framework_id)
    availability = framework.availability()
    if availability.status != "available":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=availability.reason)
    dataset = await get_evaluation_dataset_run_model(session, payload.dataset_run_id)
    if dataset.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Evaluation dataset is not completed")
    flow = await session.scalar(
        select(RagFlow).where(RagFlow.flow_id == payload.flow_id).options(selectinload(RagFlow.vector_run))
    )
    if not flow:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="RAG flow not found")
    if not _flow_has_answer_generator(flow):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="RAG flow needs an answer_generator node")
    if flow.vector_run and flow.vector_run.chunk_run_id != dataset.chunk_run_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Flow vector run is not based on dataset chunk run")
    metrics = payload.metric_ids or list(framework.default_metrics)
    row = EvaluationReportRun(
        flow_id=payload.flow_id,
        dataset_run_id=payload.dataset_run_id,
        framework_id=payload.framework_id,
        metric_ids=metrics,
        evaluator_config=payload.evaluator_config,
        total_items=dataset.completed_items,
    )
    session.add(row)
    await session.commit()
    refreshed = await get_evaluation_report_run_model(session, row.run_id)
    return _report_run_out(refreshed)


async def get_evaluation_report_run_model(session: AsyncSession, run_id: str) -> EvaluationReportRun:
    row = await session.scalar(
        select(EvaluationReportRun)
        .where(EvaluationReportRun.run_id == run_id)
        .options(selectinload(EvaluationReportRun.flow), selectinload(EvaluationReportRun.dataset_run))
    )
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Evaluation report run not found")
    return row


async def list_evaluation_report_runs(session: AsyncSession) -> list[EvaluationReportRunOut]:
    rows = (
        await session.scalars(
            select(EvaluationReportRun)
            .options(selectinload(EvaluationReportRun.flow), selectinload(EvaluationReportRun.dataset_run))
            .order_by(EvaluationReportRun.created_at.desc())
        )
    ).all()
    return [_report_run_out(row) for row in rows]


async def get_evaluation_report_run(session: AsyncSession, run_id: str) -> EvaluationReportRunOut:
    return _report_run_out(await get_evaluation_report_run_model(session, run_id))


async def delete_evaluation_report_run(session: AsyncSession, run_id: str) -> None:
    report = await get_evaluation_report_run_model(session, run_id)
    if report.status in {"pending", "running"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete a running evaluation report task")
    rag_run_ids = set(
        (
            await session.scalars(
                select(EvaluationReportItem.rag_flow_run_id).where(
                    EvaluationReportItem.run_id == run_id,
                    EvaluationReportItem.rag_flow_run_id.is_not(None),
                )
            )
        ).all()
    )
    await session.delete(report)
    await session.flush()
    await _delete_owned_rag_flow_runs(session, {item for item in rag_run_ids if item})
    await session.commit()


async def execute_evaluation_report_run(run_id: str) -> None:
    async with AsyncSessionLocal() as session:
        report = await get_evaluation_report_run_model(session, run_id)
        report.status = "running"
        report.started_at = datetime.now(UTC)
        await session.commit()
    item_scores: list[dict[str, float]] = []
    records: list[dict[str, Any]] = []
    errors: list[str] = []
    try:
        async with AsyncSessionLocal() as session:
            report = await get_evaluation_report_run_model(session, run_id)
            dataset_items = (
                await session.scalars(
                    select(EvaluationDatasetItem)
                    .where(EvaluationDatasetItem.run_id == report.dataset_run_id)
                    .order_by(EvaluationDatasetItem.created_at)
                )
            ).all()
            report.total_items = len(dataset_items)
            await session.commit()
            for dataset_item in dataset_items:
                try:
                    rag_run = await rag_service.run_rag_flow(
                        session, report.flow_id, RagFlowRunCreate(query=dataset_item.question)
                    )
                    if rag_run.status != "completed" or not rag_run.answer:
                        raise RuntimeError(rag_run.error or "RAG flow did not produce an answer")
                    contexts = [str(item.get("contents") or "") for item in rag_run.final_passages]
                    chunk_ids = [str(item.get("chunk_id") or "") for item in rag_run.final_passages if item.get("chunk_id")]
                    report_item = EvaluationReportItem(
                        run_id=report.run_id,
                        dataset_item_id=dataset_item.item_id,
                        rag_flow_run_id=rag_run.run_id,
                        question=dataset_item.question,
                        answer=rag_run.answer,
                        contexts=contexts,
                        retrieved_chunk_ids=chunk_ids,
                        scores={},
                        trace_events=rag_run.trace_events,
                        latency_ms=rag_run.latency_ms,
                    )
                    records.append(
                        {
                            "question": dataset_item.question,
                            "answer": rag_run.answer,
                            "contexts": contexts,
                            "ground_truth": dataset_item.ground_truth,
                        }
                    )
                    session.add(report_item)
                    report.completed_items += 1
                except Exception as exc:
                    errors.append(f"{dataset_item.item_id}: {exc}")
                    session.add(
                        EvaluationReportItem(
                            run_id=report.run_id,
                            dataset_item_id=dataset_item.item_id,
                            question=dataset_item.question,
                            answer=None,
                            contexts=[],
                            retrieved_chunk_ids=[],
                            scores={},
                            trace_events=[],
                            error=str(exc),
                        )
                    )
                    report.failed_items += 1
                await session.commit()
            adapter = get_evaluation_adapter(report.framework_id)
            if not records:
                raise RuntimeError("No successful RAG flow runs to evaluate")
            judge = await _get_model(session, report.dataset_run.judge_llm_model_id)
            embedding = await _resolve_embedding_model(session, report.dataset_run.embedding_model_id)
            if report.dataset_run.embedding_model_id != embedding.model_id:
                report.dataset_run.embedding_model_id = embedding.model_id
                await session.commit()
            aggregate, item_scores = await adapter.evaluate(
                records=records,
                metric_ids=report.metric_ids,
                judge_llm_model=judge,
                embedding_model=embedding,
            )
            report_items = (
                await session.scalars(
                    select(EvaluationReportItem)
                    .where(EvaluationReportItem.run_id == report.run_id, EvaluationReportItem.error.is_(None))
                    .order_by(EvaluationReportItem.created_at)
                )
            ).all()
            for row, scores in zip(report_items, item_scores, strict=False):
                row.scores = scores
            report.aggregate_scores = aggregate
            report.status = "completed_with_errors" if report.failed_items else "completed"
            report.error_summary = "\n".join(errors[-5:]) if errors else None
            report.ended_at = datetime.now(UTC)
            await session.commit()
    except Exception as exc:
        async with AsyncSessionLocal() as session:
            report = await get_evaluation_report_run_model(session, run_id)
            report.status = "failed"
            report.error_summary = str(exc)
            report.ended_at = datetime.now(UTC)
            await session.commit()


async def list_evaluation_report_items(
    session: AsyncSession, run_id: str, offset: int = 0, limit: int = 50
) -> EvaluationReportItemsPageOut:
    await get_evaluation_report_run_model(session, run_id)
    normalized_offset = max(offset, 0)
    normalized_limit = min(max(limit, 1), 500)
    total = await session.scalar(
        select(func.count()).select_from(EvaluationReportItem).where(EvaluationReportItem.run_id == run_id)
    )
    rows = (
        await session.scalars(
            select(EvaluationReportItem)
            .where(EvaluationReportItem.run_id == run_id)
            .order_by(EvaluationReportItem.created_at)
            .offset(normalized_offset)
            .limit(normalized_limit)
        )
    ).all()
    return EvaluationReportItemsPageOut(
        items=[EvaluationReportItemOut.model_validate(row, from_attributes=True) for row in rows],
        total=total or 0,
        offset=normalized_offset,
        limit=normalized_limit,
    )
