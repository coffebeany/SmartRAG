# SmartRAG

SmartRAG is a visual RAG strategy experimentation platform. This repository currently contains:

- `backend`: FastAPI backend for model registry, Agent dry-runs, material batches, parser registry, and parse runs.
- `frontend`: React + Vite + Ant Design web console for configuration and build workflows.
- `SmartRAG_Design.md`: product and architecture design notes.

## Development

Backend:

```powershell
cd backend
uv sync
Copy-Item .env.example .env
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm.cmd install
Copy-Item .env.example .env
npm.cmd run dev
```

## Parser Workflow

The parser registry follows AutoRAG parse naming where possible. It registers local/lightweight parsers (`plain_text`, `csv`, `json`, `unstructuredmarkdown`, `bshtml`, `unstructuredxml`) and AutoRAG-compatible parser entries such as `pdfminer`, `pdfplumber`, `pypdf`, `pymupdf`, `llama_parse`, `clova`, `upstagedocumentparse`, and `table_hybrid_parse`.

Heavy or API-backed parsers can be configured before they are executable. Their availability is shown in `配置 -> 材料管理 -> 解析工具`.

To try the workflow:

```powershell
cd backend
docker compose up -d postgres
uv run alembic upgrade head
uv run pytest -p no:cacheprovider
```

Then start backend and frontend, create or upload a material batch, open `构建 -> 材料解析`, choose parsers per file, and submit. Progress appears under `构建 -> 解析情况` as completed/total files, with file-level previews after completion.
