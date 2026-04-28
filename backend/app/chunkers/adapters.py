from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParsedDocumentInput:
    parsed_document_id: str
    source_file_id: str
    file_name: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    elements: list[dict[str, Any]] = field(default_factory=list)


@dataclass(frozen=True)
class ChunkResult:
    chunk_index: int
    contents: str
    source_text: str
    start_char: int
    end_char: int
    char_count: int
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    source_file_id: str = ""
    parsed_document_id: str = ""
    source_element_refs: list[dict[str, Any]] = field(default_factory=list)
    strategy_metadata: dict[str, Any] = field(default_factory=dict)


class ChunkerAdapter:
    def chunk(self, document: ParsedDocumentInput, config: dict[str, Any]) -> list[ChunkResult]:
        raise NotImplementedError


def _words(text: str) -> list[str]:
    return re.findall(r"\S+", text)


def _sentences(text: str) -> list[tuple[int, int, str]]:
    matches = list(re.finditer(r"[^.!?\n。！？]+[.!?。！？]?", text))
    result = []
    for match in matches:
        sentence = match.group(0).strip()
        if sentence:
            result.append((match.start(), match.end(), sentence))
    if not result and text.strip():
        result.append((0, len(text), text.strip()))
    return result


def _effective_overlap(config: dict[str, Any], chunk_size: int) -> int:
    if not config.get("overlap_enabled", True):
        return 0
    ratio = float(config.get("chunk_overlap_ratio") or 0)
    explicit = int(config.get("chunk_overlap") or 0)
    overlap = int(chunk_size * ratio) if ratio > 0 else explicit
    return max(0, min(overlap, max(chunk_size - 1, 0)))


def _with_metadata_prefix(content: str, document: ParsedDocumentInput, config: dict[str, Any]) -> str:
    add_file_name = str(config.get("add_file_name") or "none").lower()
    metadata_template = str(config.get("metadata_template") or "")
    prefixes: list[str] = []
    if add_file_name in {"en", "english"}:
        prefixes.append(f"file_name: {document.file_name}")
    elif add_file_name in {"ko", "korean"}:
        prefixes.append(f"파일명: {document.file_name}")
    elif add_file_name in {"ja", "japanese"}:
        prefixes.append(f"ファイル名: {document.file_name}")
    if config.get("include_metadata", True) and metadata_template:
        try:
            prefixes.append(metadata_template.format(file_name=document.file_name, **document.metadata))
        except (KeyError, ValueError):
            prefixes.append(metadata_template)
    if not prefixes:
        return content
    return "\n".join(prefixes + [f"contents: {content}"])


def _element_refs(document: ParsedDocumentInput, start: int, end: int) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    cursor = 0
    for index, element in enumerate(document.elements):
        text = str(element.get("text") or "")
        if not text:
            continue
        found = document.text.find(text, cursor)
        if found < 0:
            found = document.text.find(text)
        if found < 0:
            continue
        element_end = found + len(text)
        cursor = element_end
        if found < end and element_end > start:
            ref = {"element_index": index, "type": element.get("type")}
            for key in ("page", "line", "row_index"):
                if key in element:
                    ref[key] = element[key]
            refs.append(ref)
    return refs[:8]


def _make_chunk(
    document: ParsedDocumentInput,
    config: dict[str, Any],
    index: int,
    source_text: str,
    start: int,
    end: int,
    strategy_metadata: dict[str, Any],
) -> ChunkResult:
    contents = _with_metadata_prefix(source_text, document, config)
    metadata = dict(document.metadata)
    metadata.update({"file_name": document.file_name, "source_file_id": document.source_file_id})
    return ChunkResult(
        chunk_index=index,
        contents=contents,
        source_text=source_text,
        start_char=start,
        end_char=end,
        char_count=len(source_text),
        token_count=len(_words(source_text)),
        metadata=metadata,
        source_file_id=document.source_file_id,
        parsed_document_id=document.parsed_document_id,
        source_element_refs=_element_refs(document, start, end),
        strategy_metadata=strategy_metadata,
    )


class CharacterChunkerAdapter(ChunkerAdapter):
    def chunk(self, document: ParsedDocumentInput, config: dict[str, Any]) -> list[ChunkResult]:
        text = document.text or ""
        chunk_size = max(int(config.get("chunk_size") or 512), 1)
        overlap = _effective_overlap(config, chunk_size)
        step = max(chunk_size - overlap, 1)
        chunks = []
        for index, start in enumerate(range(0, len(text), step)):
            end = min(start + chunk_size, len(text))
            source_text = text[start:end].strip()
            if source_text:
                chunks.append(
                    _make_chunk(
                        document,
                        config,
                        index,
                        source_text,
                        start,
                        end,
                        {"splitter": "character", "chunk_size": chunk_size, "overlap": overlap},
                    )
                )
            if end >= len(text):
                break
        return chunks


class TokenChunkerAdapter(ChunkerAdapter):
    def chunk(self, document: ParsedDocumentInput, config: dict[str, Any]) -> list[ChunkResult]:
        text = document.text or ""
        tokens = list(re.finditer(r"\S+", text))
        chunk_size = max(int(config.get("chunk_size") or 512), 1)
        overlap = _effective_overlap(config, chunk_size)
        step = max(chunk_size - overlap, 1)
        chunks = []
        for index, start_token in enumerate(range(0, len(tokens), step)):
            end_token = min(start_token + chunk_size, len(tokens))
            start = tokens[start_token].start()
            end = tokens[end_token - 1].end()
            source_text = text[start:end].strip()
            if source_text:
                chunks.append(
                    _make_chunk(
                        document,
                        config,
                        index,
                        source_text,
                        start,
                        end,
                        {"splitter": "token", "chunk_size": chunk_size, "overlap": overlap},
                    )
                )
            if end_token >= len(tokens):
                break
        return chunks


class SentenceChunkerAdapter(ChunkerAdapter):
    def __init__(self, window: bool = False) -> None:
        self.window = window

    def chunk(self, document: ParsedDocumentInput, config: dict[str, Any]) -> list[ChunkResult]:
        sentences = _sentences(document.text or "")
        chunk_size = max(int(config.get("chunk_size") or 512), 1)
        window_size = max(int(config.get("window_size") or 3), 1)
        overlap = _effective_overlap(config, chunk_size)
        sentence_overlap = int(config.get("sentence_overlap") or (1 if overlap else 0))
        chunks = []
        index = 0
        start_sentence = 0
        while start_sentence < len(sentences):
            char_total = 0
            end_sentence = start_sentence
            while end_sentence < len(sentences):
                sentence_len = len(sentences[end_sentence][2])
                if end_sentence > start_sentence and char_total + sentence_len > chunk_size:
                    break
                char_total += sentence_len + 1
                end_sentence += 1
                if self.window and end_sentence - start_sentence >= window_size:
                    break
            start = sentences[start_sentence][0]
            end = sentences[end_sentence - 1][1]
            source_text = " ".join(sentence[2] for sentence in sentences[start_sentence:end_sentence]).strip()
            if source_text:
                chunks.append(
                    _make_chunk(
                        document,
                        config,
                        index,
                        source_text,
                        start,
                        end,
                        {
                            "splitter": "sentence_window" if self.window else "sentence",
                            "chunk_size": chunk_size,
                            "sentence_overlap": sentence_overlap,
                            "window_size": window_size if self.window else None,
                        },
                    )
                )
                index += 1
            if end_sentence >= len(sentences):
                break
            start_sentence = max(end_sentence - sentence_overlap, start_sentence + 1)
        return chunks


class SimpleChunkerAdapter(ChunkerAdapter):
    def chunk(self, document: ParsedDocumentInput, config: dict[str, Any]) -> list[ChunkResult]:
        text = (document.text or "").strip()
        if not text:
            return []
        return [_make_chunk(document, config, 0, text, 0, len(document.text or ""), {"splitter": "simple"})]


ADAPTERS: dict[str, ChunkerAdapter] = {
    "langchain_token": TokenChunkerAdapter(),
    "langchain_recursive_character": CharacterChunkerAdapter(),
    "langchain_character": CharacterChunkerAdapter(),
    "langchain_konlpy": SentenceChunkerAdapter(),
    "llama_index_token": TokenChunkerAdapter(),
    "llama_index_sentence": SentenceChunkerAdapter(),
    "llama_index_sentence_window": SentenceChunkerAdapter(window=True),
    "llama_index_simple": SimpleChunkerAdapter(),
    "llama_index_semantic": SentenceChunkerAdapter(),
    "llama_index_semantic_doubling": SentenceChunkerAdapter(),
}


def get_adapter(chunker_name: str) -> ChunkerAdapter:
    adapter = ADAPTERS.get(chunker_name)
    if not adapter:
        raise RuntimeError(f"Chunker {chunker_name} is not executable.")
    return adapter
