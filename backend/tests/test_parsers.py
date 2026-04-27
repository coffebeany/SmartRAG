from pathlib import Path

import pytest

from app.parsers.adapters import get_adapter
from app.parsers.registry import parser_registry

FIXTURE_DIR = Path(__file__).parent / "fixtures"


def test_autorag_parser_registry_contains_expected_modules() -> None:
    names = {parser.parser_name for parser in parser_registry.list_enabled()}

    assert {"pdfminer", "pdfplumber", "pypdfium2", "pypdf", "pymupdf"}.issubset(names)
    assert {"csv", "json", "unstructuredmarkdown", "bshtml", "unstructuredxml"}.issubset(names)
    assert {"directory", "unstructured", "upstagedocumentparse"}.issubset(names)
    assert {"llama_parse", "clova", "table_hybrid_parse"}.issubset(names)


def test_autorag_default_parsers_match_documentation() -> None:
    assert parser_registry.default_parser_for_extension(".pdf").parser_name == "pdfminer"
    assert parser_registry.default_parser_for_extension(".csv").parser_name == "csv"
    assert parser_registry.default_parser_for_extension(".md").parser_name == "unstructuredmarkdown"
    assert parser_registry.default_parser_for_extension(".html").parser_name == "bshtml"
    assert parser_registry.default_parser_for_extension(".xml").parser_name == "unstructuredxml"
    assert parser_registry.default_parser_for_extension(".json") is None


def test_json_parser_requires_jq_schema() -> None:
    source = FIXTURE_DIR / "sample.json"

    with pytest.raises(ValueError):
        get_adapter("json").parse(source, {})

    result = get_adapter("json").parse(source, {"jq_schema": ".content"})
    assert result.text == "hello"


def test_lightweight_text_parser_outputs_elements() -> None:
    source = FIXTURE_DIR / "note.txt"

    result = get_adapter("plain_text").parse(source, {})

    assert result.text.rstrip("\n") == "alpha\n\nbeta"
    assert [item["text"] for item in result.elements] == ["alpha", "beta"]
