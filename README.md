# SmartRAG

SmartRAG is a visual RAG strategy experimentation platform. This repository currently contains:

- `backend`: FastAPI backend for model registry, Agent dry-runs, material batches, parser/chunk/vector registries, and processing runs.
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

Non-LLM parser dependency layers are declared as uv extras:

```powershell
cd backend
uv sync --extra parsers-pdf           # pdfminer/pdfplumber/pymupdf/pypdf/pypdfium2
uv sync --extra parsers-unstructured  # unstructured[pdf,md]
uv sync --extra parsers-local         # all local non-LLM parser dependencies
```

These are not installed by default to keep the base backend small and deployable. The UI still shows them with `missing_dependency` or `adapter_only` status until dependencies and adapters are available.

To try the workflow:

```powershell
cd backend
docker compose up -d postgres
uv run alembic upgrade head
uv run pytest -p no:cacheprovider
```

Then start backend and frontend, create or upload a material batch, open `构建 -> 材料解析`, choose parsers per file, and submit. Progress appears under `构建 -> 解析情况` as completed/total files, with file-level previews after completion.

In parse details, Elements are loaded through a paginated API so large documents can be inspected without freezing the UI. Elements are parser-level observations and do not represent final RAG chunks.

Parse runs no longer calculate an automatic quality score. The legacy `quality_score` field remains for compatibility and future evaluator output, but new parse results leave it empty and the UI shows `NA`. Parser quality evaluation is reserved behind placeholder evaluator APIs so ParseBench, SCORE-Bench, or other adapters can be connected later without changing the parse workflow.

## Chunk Workflow

Chunk runs use a completed parse run as input. Open `构建 -> 材料分块`, choose a material batch, choose a completed parse run, select one chunk strategy, edit the JSON config, and submit. Progress appears under `构建 -> 分块任务`; completed runs expose file-level chunk previews and a batch-level comparison view under `构建 -> 分块对比`.

SmartRAG registers AutoRAG-compatible chunk strategies from LangChain Chunk and LlamaIndex Chunk families. The backend stores normalized chunk rows in the database for paging and downstream retrieval, while writing JSON artifacts under `storage/chunks` for debugging and reproducibility.

## Vector Workflow

Vector runs use a completed chunk run as input. Open `构建 -> 材料向量化`, choose a material batch, choose a completed chunk run, select an enabled Embedded model, select a VectorDB backend, tune the JSON strategy options, choose participating files, and submit. Progress appears under `构建 -> 向量化任务`.

The default VectorDB is Chroma persistent storage under `storage/vectors/chroma`. SmartRAG stores vector run metadata, model snapshots, strategy configs, file progress, and chunk-to-vector mappings in Postgres. The vector bodies are written to the selected VectorDB collection. Deleting a vector run synchronously deletes its external collection.

VectorDB strategy metadata is schema-driven and recorded with each run, including similarity metric, embedding batch size, normalization, payload metadata mode, and adapter-specific index options. The `仅测试集相关` file-selection mode is reserved for the future test-set workflow and is currently disabled in the UI.
