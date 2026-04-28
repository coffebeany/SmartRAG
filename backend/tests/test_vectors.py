from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.vectors import VectorRunCreate
from app.services.vectors import _filter_file_runs, _validate_embedding_model
from app.vectorstores.registry import vectordb_registry


def test_vectordb_registry_contains_core_and_autorag_modules() -> None:
    names = {item.vectordb_name for item in vectordb_registry.list_enabled()}

    assert {"chroma", "qdrant", "pgvector", "milvus", "weaviate", "pinecone", "couchbase"}.issubset(names)
    chroma = vectordb_registry.get("chroma")
    assert chroma is not None
    assert chroma.default_storage_uri == "storage/vectors/chroma"
    assert "advanced_options_schema" not in chroma.default_config


def test_vectordb_api_returns_status_and_strategy_schema() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/vectordbs")

    assert response.status_code == 200
    by_name = {item["vectordb_name"]: item for item in response.json()}
    assert by_name["chroma"]["default_storage_uri"] == "storage/vectors/chroma"
    assert "similarity_metric" in by_name["chroma"]["advanced_options_schema"]["properties"]
    assert by_name["milvus"]["availability_status"] == "adapter_only"


def test_vector_run_schema_records_strategy_and_file_selection() -> None:
    payload = VectorRunCreate(
        batch_id="batch-1",
        chunk_run_id="chunk-run-1",
        embedding_model_id="model-1",
        vectordb_name="chroma",
        vectordb_config={"path": "storage/vectors/chroma"},
        embedding_config={"normalize_embeddings": True},
        index_config={"similarity_metric": "cosine"},
        file_selection={"mode": "selected", "selected_file_ids": ["file-1"]},
    )

    assert payload.file_selection.mode == "selected"
    assert payload.embedding_config["normalize_embeddings"] is True


def test_test_related_file_selection_is_reserved() -> None:
    with pytest.raises(HTTPException) as exc_info:
        _filter_file_runs([], "test_related", [])

    assert exc_info.value.status_code == 501


def test_embedding_model_validation_rejects_non_embedding_disabled_and_failed() -> None:
    with pytest.raises(HTTPException, match="not an embedding"):
        _validate_embedding_model(
            SimpleNamespace(model_category="llm", enabled=True, connection_status="available")
        )
    with pytest.raises(HTTPException, match="disabled"):
        _validate_embedding_model(
            SimpleNamespace(model_category="embedding", enabled=False, connection_status="available")
        )
    with pytest.raises(HTTPException, match="failed"):
        _validate_embedding_model(
            SimpleNamespace(model_category="embedding", enabled=True, connection_status="failed")
        )
