import pytest
from fastapi.testclient import TestClient

from app.chunkers.adapters import ParsedDocumentInput, get_adapter
from app.chunkers.registry import chunker_registry
from app.main import create_app
from app.schemas.chunks import ChunkRunCreate
from app.services.chunks import _stats_from_lengths, _validate_chunker


def test_autorag_chunker_registry_contains_expected_modules() -> None:
    names = {chunker.chunker_name for chunker in chunker_registry.list_enabled()}

    assert {
        "langchain_token",
        "langchain_recursive_character",
        "langchain_character",
        "langchain_konlpy",
        "llama_index_token",
        "llama_index_sentence",
        "llama_index_sentence_window",
        "llama_index_semantic",
        "llama_index_semantic_doubling",
        "llama_index_simple",
    }.issubset(names)


def test_character_chunker_outputs_unified_chunks_with_metadata_prefix() -> None:
    document = ParsedDocumentInput(
        parsed_document_id="doc-1",
        source_file_id="file-1",
        file_name="note.txt",
        text="alpha beta gamma delta",
        metadata={"page": 1},
        elements=[{"type": "paragraph", "text": "alpha beta gamma delta", "page": 1}],
    )

    chunks = get_adapter("langchain_character").chunk(
        document,
        {
            "chunk_size": 10,
            "overlap_enabled": True,
            "chunk_overlap": 2,
            "include_metadata": True,
            "metadata_template": "page: {page}",
            "add_file_name": "en",
        },
    )

    assert len(chunks) >= 2
    assert chunks[0].contents.startswith("file_name: note.txt\npage: 1\ncontents:")
    assert chunks[0].parsed_document_id == "doc-1"
    assert chunks[0].source_file_id == "file-1"
    assert chunks[0].source_element_refs[0]["page"] == 1


def test_token_chunker_uses_overlap_ratio() -> None:
    document = ParsedDocumentInput(
        parsed_document_id="doc-1",
        source_file_id="file-1",
        file_name="note.txt",
        text="one two three four five six",
    )

    chunks = get_adapter("langchain_token").chunk(
        document,
        {"chunk_size": 4, "overlap_enabled": True, "chunk_overlap_ratio": 0.5},
    )

    assert [chunk.source_text for chunk in chunks] == [
        "one two three four",
        "three four five six",
    ]


def test_semantic_chunker_requires_embedding_model_id() -> None:
    strategy = chunker_registry.get("llama_index_semantic")
    assert strategy is not None

    with pytest.raises(Exception) as exc_info:
        _validate_chunker(strategy, strategy.default_config)

    assert "embedding_model_id" in str(exc_info.value)


def test_chunk_stats_from_lengths() -> None:
    stats = _stats_from_lengths([10, 20, 30], total_files=2, completed_files=2, failed_files=0)

    assert stats["chunk_count"] == 3
    assert stats["avg_char_count"] == 20
    assert stats["min_char_count"] == 10
    assert stats["max_char_count"] == 30


def test_chunk_run_create_schema_accepts_single_strategy() -> None:
    payload = ChunkRunCreate(
        batch_id="batch-1",
        parse_run_id="parse-run-1",
        chunker_name="langchain_character",
        chunker_config={"chunk_size": 128},
    )

    assert payload.chunker_name == "langchain_character"


def test_chunk_strategy_api_returns_registered_chunkers() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/chunk-strategies")

    assert response.status_code == 200
    names = {item["chunker_name"] for item in response.json()}
    assert "langchain_character" in names
    assert "llama_index_sentence" in names
