# SmartRAG Backend

FastAPI backend for SmartRAG model configuration, material management, parser registry, and material parse runs.

## Local setup

```powershell
uv sync
Copy-Item .env.example .env
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs are available at `http://127.0.0.1:8000/docs`.

## Parser Integrations

SmartRAG keeps parser support in `app/parsers/registry.py` and executable adapters in `app/parsers/adapters.py`.

Registered AutoRAG-compatible parser names:

- `langchain_parse`: `pdfminer`, `pdfplumber`, `pypdfium2`, `pypdf`, `pymupdf`, `unstructuredpdf`, `csv`, `json`, `unstructuredmarkdown`, `bshtml`, `unstructuredxml`, `directory`, `unstructured`, `upstagedocumentparse`
- API/specialized parsers: `llama_parse`, `clova`, `table_hybrid_parse`
- SmartRAG lightweight parser: `plain_text` for `.txt` and `.log`

Default parser rules mirror AutoRAG where applicable: PDF uses `pdfminer`, CSV uses `csv`, Markdown uses `unstructuredmarkdown`, HTML uses `bshtml`, XML uses `unstructuredxml`; JSON intentionally has no default because it needs `jq_schema`.

Availability is computed at runtime:

- `available`: dependencies and required environment variables are present.
- `missing_dependency`: optional Python package is not installed.
- `missing_env`: required API key or endpoint is missing.
- `needs_config`: parser is registered but requires per-run config, for example JSON `jq_schema`.
- `unavailable`: registered for configuration/UI parity but no local adapter exists yet.

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
