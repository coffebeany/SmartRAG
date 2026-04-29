from app.models.entities import ParseFileRun
from app.parsers.adapters import ParsedResult
from app.services.parse_runs import (
    _apply_parse_success,
    _format_parse_delete_dependency_message,
    _paginate_elements,
)


def test_paginate_elements_defaults_and_slices() -> None:
    elements = [{"index": index} for index in range(80)]

    page = _paginate_elements(elements)

    assert page.total == 80
    assert page.offset == 0
    assert page.limit == 50
    assert len(page.items) == 50
    assert page.items[0] == {"index": 0}
    assert page.items[-1] == {"index": 49}


def test_paginate_elements_clamps_limit_and_offset() -> None:
    elements = [{"index": index} for index in range(600)]

    page = _paginate_elements(elements, offset=-10, limit=900)

    assert page.offset == 0
    assert page.limit == 500
    assert len(page.items) == 500


def test_apply_parse_success_does_not_write_quality_score() -> None:
    file_run = ParseFileRun(
        file_run_id="file-run-1",
        run_id="run-1",
        file_id="file-1",
        parser_name="plain_text",
        parser_config={},
        quality_score=90,
    )
    result = ParsedResult(
        text="hello",
        elements=[{"type": "paragraph", "text": "hello"}],
        metadata={"file_name": "note.txt"},
        pages=-1,
    )

    document = _apply_parse_success(file_run, result, "run-1", 12, "storage/parsed/run-1/file.json")

    assert file_run.status == "completed"
    assert file_run.quality_score is None
    assert file_run.output_artifact_uri == "storage/parsed/run-1/file.json"
    assert document.text_content == "hello"
    assert document.char_count == 5


def test_format_parse_delete_dependency_message_names_downstream_usage() -> None:
    message = _format_parse_delete_dependency_message(
        chunk_runs=["chunk-1", "chunk-2"],
        vector_runs=["vector-1"],
        rag_flows=["混合检索测试(flow-1)"],
    )

    assert message is not None
    assert "该解析任务目前被" in message
    assert "2 个分块任务" in message
    assert "1 个向量化任务" in message
    assert "1 个 RAG 流程" in message
    assert "混合检索测试(flow-1)" in message
    assert "无法删除" in message
