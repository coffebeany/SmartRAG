# SmartRAG Backend

FastAPI backend for SmartRAG model configuration, material management, parser/chunk/vector registries, and batch processing runs.

## Local setup

```powershell
uv sync
Copy-Item .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API docs are available at `http://127.0.0.1:8000/docs`.

## Parser Integrations

SmartRAG keeps parser support in `app/parsers/registry.py` and executable adapters in `app/parsers/adapters.py`.

Registered AutoRAG-compatible parser names:

- `langchain_parse`: `pdfminer`, `pdfplumber`, `pypdfium2`, `pypdf`, `pymupdf`, `unstructuredpdf`, `csv`, `json`, `unstructuredmarkdown`, `bshtml`, `unstructuredxml`, `directory`, `unstructured`, `upstagedocumentparse`
- API/specialized parsers: `llama_parse`, `clova`, `table_hybrid_parse`
- SmartRAG lightweight parser: `plain_text` for `.txt` and `.log`

Default parser rules mirror AutoRAG where applicable: PDF uses `pdfminer`, CSV uses `csv`, Markdown uses `unstructuredmarkdown`, HTML uses `bshtml`, XML uses `unstructuredxml`; JSON intentionally has no default because it needs `jq_schema`.

The API returns `config_schema` and `default_config` for every parser. The UI uses these values to prefill per-file parser JSON, so non-LLM parsers can run with minimal manual setup:

- `plain_text`, `csv`, `unstructuredmarkdown`, `bshtml`, `unstructuredxml`: `{"encoding": "utf-8"}`
- PDF parsers: `{"mode": "single"}`
- `json`: `{"encoding": "utf-8", "jq_schema": ""}` and must be edited for the target JSON shape.
- `table_hybrid_parse`: prefilled with `pdfminer` for text and `pdfplumber` for table parsing, but still marked adapter-only in this MVP.

## Parser Dependencies

Installed by default:

- TXT/log, CSV, JSON, Markdown, HTML, and XML lightweight parsing use the Python standard library or SmartRAG's built-in adapters.

Not installed by default:

- PDF local parsers: `pdfminer.six`, `pdfplumber`, `pymupdf`, `pypdf`, `pypdfium2`
- Heavy local document parsing: `unstructured[pdf,md]`
- API parsers: `llama_parse`, `clova`, `upstagedocumentparse`; these require credentials and are intentionally not part of the local parser extras.

Quick install commands:

```powershell
# PDF-only local parser set
uv sync --extra parsers-pdf

# Unstructured local parser set
uv sync --extra parsers-unstructured

# All non-LLM local parser dependencies
uv sync --extra parsers-local
```

Availability is computed at runtime:

- `available`: dependencies and required environment variables are present.
- `missing_dependency`: optional Python package is not installed.
- `missing_env`: required API key or endpoint is missing.
- `needs_config`: parser is registered but requires per-run config, for example JSON `jq_schema`.
- `adapter_only`: registered for configuration/UI parity but no local executable adapter exists yet.

Optional environment variables:

```powershell
LLAMA_CLOUD_API_KEY=
UPSTAGE_API_KEY=
CLOVA_OCR_API_URL=
CLOVA_OCR_SECRET_KEY=
```

## Parse APIs

Main endpoints under `/api/v1`:

- `GET /parser-strategies`
- `GET /material-batches/{batch_id}/parse-plan`
- `POST /parse-runs`
- `GET /parse-runs`
- `GET /parse-runs/{run_id}`
- `GET /parse-runs/{run_id}/files`
- `GET /parse-runs/{run_id}/files/{file_run_id}`
- `GET /parse-runs/{run_id}/files/{file_run_id}/elements?offset=0&limit=50`

Example parse request:

```json
{
  "batch_id": "batch-id",
  "selections": [
    {
      "file_id": "file-id",
      "parser_name": "plain_text",
      "parser_config": {}
    }
  ]
}
```

Elements are parser observations, not retrieval chunks. Their granularity depends on the parser:

- TXT/Markdown usually creates paragraph or heading elements.
- CSV creates row elements.
- JSON creates one element per matched `jq_schema` value.
- PDF parsers currently produce page-level or paragraph-level elements depending on the adapter.

Use the paginated elements endpoint for complete element inspection. The file detail endpoint is intended for summary metadata and text preview.

Parse runs do not automatically score output quality. The `quality_score` field is kept for historical compatibility and future evaluator output, but new file runs leave it `null` and the UI renders it as `NA`.

## Parse Evaluation Placeholders

SmartRAG exposes evaluator discovery and run-creation placeholders for future parser quality adapters:

- `GET /parse-evaluators`
- `POST /parse-evaluation-runs`

The current built-in evaluator entries are `parsebench` and `score_bench`. Both return `adapter_only` availability because no executable ParseBench or SCORE-Bench adapter is bundled yet. Creating an evaluation run currently returns `501 Not Implemented` and does not write database records. No ParseBench or SCORE-Bench dependencies are installed by default.

## Chunk APIs

Chunk tasks require a completed parse run and execute one chunk strategy per run. Main endpoints:

- `GET /chunk-strategies`
- `POST /chunk-strategies/refresh`
- `GET /material-batches/{batch_id}/chunk-plan?parse_run_id=...`
- `POST /chunk-runs`
- `GET /chunk-runs`
- `GET /chunk-runs/{run_id}`
- `GET /chunk-runs/{run_id}/files`
- `GET /chunk-runs/{run_id}/files/{file_run_id}/chunks?offset=0&limit=50`
- `GET /material-batches/{batch_id}/chunk-runs/compare`

Registered AutoRAG-compatible chunk strategies:

- LangChain Chunk: `langchain_token`, `langchain_recursive_character`, `langchain_character`, `langchain_konlpy`
- LlamaIndex Chunk: `llama_index_token`, `llama_index_sentence`, `llama_index_sentence_window`, `llama_index_semantic`, `llama_index_semantic_doubling`, `llama_index_simple`

Chunk output is normalized to `contents`, `source_text`, character offsets, token count, metadata, source element refs, and strategy metadata. Rows are stored in the database for UI paging and future retrieval/indexing; JSON artifacts are written under `storage/chunks`.

Optional dependency groups:

```powershell
uv sync --extra chunk-langchain
uv sync --extra chunk-llama-index
uv sync --extra chunk-korean
uv sync --extra chunk-semantic
```

Semantic chunkers require `embedding_model_id` in `chunker_config`; SmartRAG does not silently choose a default embedding model.

## VectorDB APIs

Vector tasks require a completed chunk run and execute one VectorDB backend per run. Main endpoints:

- `GET /vectordbs`
- `POST /vectordbs/refresh`
- `GET /material-batches/{batch_id}/vector-plan?chunk_run_id=...`
- `POST /vector-runs`
- `GET /vector-runs`
- `GET /vector-runs/{run_id}`
- `DELETE /vector-runs/{run_id}`
- `GET /vector-runs/{run_id}/files`
- `GET /material-batches/{batch_id}/vector-runs/compare`

The create payload records the complete strategy:

```json
{
  "batch_id": "batch-id",
  "chunk_run_id": "chunk-run-id",
  "embedding_model_id": "embedding-model-id",
  "vectordb_name": "chroma",
  "vectordb_config": {
    "path": "storage/vectors/chroma",
    "similarity_metric": "cosine"
  },
  "embedding_config": {
    "normalize_embeddings": false,
    "embedding_batch": 100
  },
  "index_config": {
    "similarity_metric": "cosine",
    "metadata_mode": "full"
  },
  "file_selection": {
    "mode": "selected",
    "selected_file_ids": ["file-id"]
  }
}
```

Registered VectorDB modules:

- `chroma`: default executable backend; persistent local storage under `storage/vectors/chroma`.
- `qdrant`: executable adapter when `vector-qdrant` dependencies and local/remote config are available.
- `pgvector`: executable adapter against the configured Postgres database when the `vector` extension is available.
- `milvus`, `weaviate`, `pinecone`, `couchbase`: AutoRAG-compatible registry placeholders shown as `adapter_only` until executable adapters are added.

Vector run metadata stays in Postgres: model snapshots, VectorDB config, embedding/index strategy, file progress, events, and chunk-to-vector mappings. Vector bodies are stored in the selected VectorDB collection. Deleting a vector run first deletes the external collection and then removes Postgres metadata.

Optional dependency groups:

```powershell
uv sync --extra vector-qdrant
uv sync --extra vector-pgvector
```

`test_related` file selection is reserved for the future test-set generator. It is present in the API schema but currently returns `501 Not Implemented` without database side effects.

## Testing

```powershell
uv run ruff check app tests alembic
uv run pytest -p no:cacheprovider
uv run alembic heads
```

For database verification:

```powershell
docker compose up -d postgres
uv run alembic upgrade head
```
