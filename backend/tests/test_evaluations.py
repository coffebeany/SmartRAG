from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.evaluations import ParseEvaluationRunCreate
from app.services.evaluations import (
    _dataset_run_display_name,
    _merge_generator_config,
    create_parse_evaluation_run,
    list_evaluation_frameworks,
    list_parse_evaluators,
)
from app.evaluators.adapters import _ragas_embeddings_for_model, _source_chunk_scores
from app.evaluators.registry import evaluation_framework_registry


@pytest.mark.asyncio
async def test_parse_evaluators_are_registered_as_placeholders() -> None:
    evaluators = await list_parse_evaluators()

    by_name = {evaluator.evaluator_name: evaluator for evaluator in evaluators}
    assert {"parsebench", "score_bench"}.issubset(by_name)
    assert by_name["parsebench"].availability_status == "adapter_only"
    assert by_name["score_bench"].availability_status == "adapter_only"


@pytest.mark.asyncio
async def test_create_parse_evaluation_run_is_not_implemented() -> None:
    payload = ParseEvaluationRunCreate(
        batch_id="batch-1",
        parse_run_id="run-1",
        evaluator_name="parsebench",
        evaluator_config={},
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_parse_evaluation_run(payload)

    assert exc_info.value.status_code == 501


def test_parse_evaluator_api_returns_placeholders() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/parse-evaluators")

    assert response.status_code == 200
    by_name = {item["evaluator_name"]: item for item in response.json()}
    assert by_name["parsebench"]["availability_status"] == "adapter_only"
    assert by_name["score_bench"]["availability_status"] == "adapter_only"


def test_parse_evaluation_run_api_returns_501() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/parse-evaluation-runs",
        json={
            "batch_id": "batch-1",
            "parse_run_id": "run-1",
            "evaluator_name": "parsebench",
            "evaluator_config": {},
        },
    )

    assert response.status_code == 501


@pytest.mark.asyncio
async def test_evaluation_framework_registry_exposes_ragas() -> None:
    frameworks = await list_evaluation_frameworks()
    ragas = next(item for item in frameworks if item.framework_id == "ragas")

    assert ragas.default_metrics == [
        "context_precision",
        "context_recall",
        "faithfulness",
        "answer_relevancy",
    ]
    metric_ids = {metric.metric_id for metric in ragas.metrics}
    assert {
        "source_chunk_hit@3",
        "source_chunk_hit@5",
        "source_chunk_hit@10",
        "source_chunk_recall",
        "source_chunk_mrr",
        "source_chunk_rank",
    }.issubset(metric_ids)
    assert {"testset_size", "advanced_config"}.issubset(ragas.generator_config_schema["properties"])
    assert ragas.default_generator_config["language"] == "zh"
    assert ragas.availability_status in {"available", "missing_dependency"}


def test_generator_config_merges_defaults_and_advanced_config() -> None:
    framework = evaluation_framework_registry.get("ragas")
    assert framework is not None

    merged = _merge_generator_config(
        framework,
        {
            "testset_size": 20,
            "query_distribution": {"single_hop_specific": 1.0},
            "chunk_sampling": {"max_chunks": 30},
            "advanced_config": {"transforms": ["headline"]},
        },
    )

    assert merged["testset_size"] == 20
    assert merged["query_distribution"]["single_hop_specific"] == 1.0
    assert merged["query_distribution"]["multi_hop_specific"] == 0.2
    assert merged["chunk_sampling"]["mode"] == "all_completed_chunks"
    assert merged["chunk_sampling"]["max_chunks"] == 30
    assert merged["advanced_config"] == {"transforms": ["headline"]}


def test_dataset_run_display_name_includes_distinguishing_config() -> None:
    row = SimpleNamespace(
        run_id="12345678-90ab-cdef",
        batch_id="batch-1",
        batch=SimpleNamespace(batch_name="合同资料"),
        framework_id="ragas",
        generator_config={
            "testset_size": 20,
            "language": "zh",
            "chunk_sampling": {"max_chunks": 30},
        },
        stats={"selected_chunks": 12},
        total_items=20,
    )

    display_name = _dataset_run_display_name(row)

    assert "合同资料" in display_name
    assert "20样本" in display_name
    assert "zh" in display_name
    assert "chunks:12" in display_name
    assert "12345678" in display_name


def test_ragas_embedding_adapter_requires_explicit_model() -> None:
    with pytest.raises(RuntimeError, match="default_embedding_model"):
        _ragas_embeddings_for_model(None)


def test_source_chunk_metrics_use_source_and_retrieved_chunk_ids() -> None:
    scores = _source_chunk_scores(
        {
            "source_chunk_ids": ["c3", "c9"],
            "retrieved_chunk_ids": ["c2", "c8", "c9", "c1", "c3"],
        },
        {
            "source_chunk_hit@3",
            "source_chunk_hit@5",
            "source_chunk_hit@10",
            "source_chunk_recall",
            "source_chunk_mrr",
            "source_chunk_rank",
        },
    )

    assert scores["source_chunk_hit@3"] == 1.0
    assert scores["source_chunk_hit@5"] == 1.0
    assert scores["source_chunk_hit@10"] == 1.0
    assert scores["source_chunk_recall"] == 1.0
    assert scores["source_chunk_mrr"] == pytest.approx(1 / 3)
    assert scores["source_chunk_rank"] == 3.0
