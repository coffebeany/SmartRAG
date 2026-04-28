from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


@dataclass
class ParsedResult:
    text: str
    elements: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    pages: int = -1


class ParserAdapter:
    def parse(self, path: Path, config: dict[str, Any]) -> ParsedResult:
        raise NotImplementedError


def read_text(path: Path, config: dict[str, Any]) -> str:
    encoding = config.get("encoding") or "utf-8"
    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


class TextParserAdapter(ParserAdapter):
    def parse(self, path: Path, config: dict[str, Any]) -> ParsedResult:
        text = read_text(path, config)
        elements = [
            {"type": "paragraph", "text": line.strip(), "line": index + 1}
            for index, line in enumerate(text.splitlines())
            if line.strip()
        ]
        return ParsedResult(text=text, elements=elements, metadata={"file_name": path.name})


class MarkdownParserAdapter(ParserAdapter):
    def parse(self, path: Path, config: dict[str, Any]) -> ParsedResult:
        text = read_text(path, config)
        elements: list[dict[str, Any]] = []
        for index, line in enumerate(text.splitlines()):
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                level = len(stripped) - len(stripped.lstrip("#"))
                elements.append({"type": "heading", "level": level, "text": stripped[level:].strip(), "line": index + 1})
            else:
                elements.append({"type": "paragraph", "text": stripped, "line": index + 1})
        return ParsedResult(text=text, elements=elements, metadata={"file_name": path.name})


class CsvParserAdapter(ParserAdapter):
    def parse(self, path: Path, config: dict[str, Any]) -> ParsedResult:
        encoding = config.get("encoding") or "utf-8"
        rows: list[list[str]] = []
        with path.open("r", encoding=encoding, errors="replace", newline="") as handle:
            reader = csv.reader(handle)
            rows = [[cell for cell in row] for row in reader]
        lines = [", ".join(row) for row in rows]
        elements = [
            {"type": "table_row", "row_index": index, "cells": row}
            for index, row in enumerate(rows)
        ]
        return ParsedResult(text="\n".join(lines), elements=elements, metadata={"rows": len(rows), "file_name": path.name})


def _extract_json_values(data: Any, jq_schema: str) -> list[Any]:
    if not jq_schema:
        raise ValueError("JSON parser requires jq_schema, for example `.content` or `.messages[].content`.")
    path = jq_schema.strip()
    if not path.startswith("."):
        raise ValueError("Only simple jq-style paths starting with `.` are supported in MVP.")
    values = [data]
    for raw_part in [part for part in path[1:].split(".") if part]:
        is_array = raw_part.endswith("[]")
        part = raw_part[:-2] if is_array else raw_part
        next_values: list[Any] = []
        for value in values:
            if isinstance(value, dict) and part in value:
                selected = value[part]
                if is_array:
                    if isinstance(selected, list):
                        next_values.extend(selected)
                else:
                    next_values.append(selected)
        values = next_values
    return values


class JsonParserAdapter(ParserAdapter):
    def parse(self, path: Path, config: dict[str, Any]) -> ParsedResult:
        data = json.loads(read_text(path, config))
        values = _extract_json_values(data, str(config.get("jq_schema") or ""))
        text_parts = [value if isinstance(value, str) else json.dumps(value, ensure_ascii=False) for value in values]
        elements = [{"type": "json_value", "index": index, "text": text} for index, text in enumerate(text_parts)]
        return ParsedResult(text="\n".join(text_parts), elements=elements, metadata={"matches": len(values), "file_name": path.name})


class _TextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(text)


class HtmlParserAdapter(ParserAdapter):
    def parse(self, path: Path, config: dict[str, Any]) -> ParsedResult:
        parser = _TextHTMLParser()
        parser.feed(read_text(path, config))
        text = "\n".join(parser.parts)
        elements = [{"type": "html_text", "text": part} for part in parser.parts]
        return ParsedResult(text=text, elements=elements, metadata={"file_name": path.name})


class XmlParserAdapter(ParserAdapter):
    def parse(self, path: Path, config: dict[str, Any]) -> ParsedResult:
        root = ET.fromstring(read_text(path, config))
        parts: list[str] = []
        elements: list[dict[str, Any]] = []
        for node in root.iter():
            text = (node.text or "").strip()
            if text:
                parts.append(text)
                elements.append({"type": "xml_node", "tag": node.tag, "text": text})
        return ParsedResult(text="\n".join(parts), elements=elements, metadata={"root_tag": root.tag, "file_name": path.name})


def _page_paragraph_elements(text: str) -> tuple[list[dict[str, Any]], int]:
    pages = [page for page in text.split("\f") if page.strip()]
    elements: list[dict[str, Any]] = []
    for page_index, page_text in enumerate(pages):
        paragraphs = [part.strip() for part in page_text.split("\n\n") if part.strip()]
        if paragraphs:
            elements.extend(
                {
                    "type": "paragraph",
                    "page": page_index + 1,
                    "index": paragraph_index,
                    "text": paragraph,
                }
                for paragraph_index, paragraph in enumerate(paragraphs)
            )
        else:
            elements.append({"type": "page", "page": page_index + 1, "text": page_text})
    if not elements and text.strip():
        elements.append({"type": "document", "text": text})
    return elements, len(pages) if pages else -1


class PdfAdapter(ParserAdapter):
    def __init__(self, method: str) -> None:
        self.method = method

    def parse(self, path: Path, config: dict[str, Any]) -> ParsedResult:
        if self.method == "pdfminer":
            from pdfminer.high_level import extract_text

            text = extract_text(str(path))
            elements, pages = _page_paragraph_elements(text)
            return ParsedResult(
                text=text,
                elements=elements,
                metadata={"file_name": path.name},
                pages=pages,
            )
        if self.method == "pymupdf":
            import fitz

            document = fitz.open(path)
            pages = [page.get_text() for page in document]
            text = "\n".join(pages)
            return ParsedResult(
                text=text,
                elements=[{"type": "page", "page": index + 1, "text": page_text} for index, page_text in enumerate(pages)],
                metadata={"file_name": path.name},
                pages=len(pages),
            )
        if self.method == "pdfplumber":
            import pdfplumber

            with pdfplumber.open(path) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
            text = "\n".join(pages)
            return ParsedResult(text=text, elements=[{"type": "page", "page": index + 1, "text": page_text} for index, page_text in enumerate(pages)], metadata={"file_name": path.name}, pages=len(pages))
        if self.method == "pypdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages)
            return ParsedResult(text=text, elements=[{"type": "page", "page": index + 1, "text": page_text} for index, page_text in enumerate(pages)], metadata={"file_name": path.name}, pages=len(pages))
        if self.method == "pypdfium2":
            import pypdfium2 as pdfium

            document = pdfium.PdfDocument(str(path))
            pages = []
            for index in range(len(document)):
                page = document[index]
                text_page = page.get_textpage()
                pages.append(text_page.get_text_range())
            text = "\n".join(pages)
            return ParsedResult(
                text=text,
                elements=[{"type": "page", "page": index + 1, "text": page_text} for index, page_text in enumerate(pages)],
                metadata={"file_name": path.name},
                pages=len(pages),
            )
        raise RuntimeError(f"Parser {self.method} is registered but has no executable local adapter.")


ADAPTERS: dict[str, ParserAdapter] = {
    "plain_text": TextParserAdapter(),
    "unstructuredmarkdown": MarkdownParserAdapter(),
    "csv": CsvParserAdapter(),
    "json": JsonParserAdapter(),
    "bshtml": HtmlParserAdapter(),
    "unstructuredxml": XmlParserAdapter(),
    "pdfminer": PdfAdapter("pdfminer"),
    "pymupdf": PdfAdapter("pymupdf"),
    "pdfplumber": PdfAdapter("pdfplumber"),
    "pypdf": PdfAdapter("pypdf"),
    "pypdfium2": PdfAdapter("pypdfium2"),
}


def get_adapter(parser_name: str) -> ParserAdapter:
    adapter = ADAPTERS.get(parser_name)
    if not adapter:
        raise RuntimeError(f"Parser {parser_name} is not executable in this MVP.")
    return adapter
