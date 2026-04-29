# SmartRAG

> 面向 RAG 策略实验、可视化编排、评测对比与 Agentic 调优的工作台。

**语言 / Language**：中文 | [English](#english)

SmartRAG 是一个 UI-first 的 RAG 实验平台。它参考 AutoRAG 的模块化实验思想，把材料解析、分块、向量化、检索流程编排、问答体验、评测报告和 Agent 辅助调优组织成一个可观察、可复现、可扩展的完整工作流。

当前仓库包含：

- `backend`：FastAPI 后端，负责模型管理、材料管理、Parser/Chunker/VectorDB/RAG 组件注册、任务运行、评测、MCP Server 与 SmartRAG Agent。
- `frontend`：React + Vite + Ant Design 前端工作台，负责配置中心、构建中心、流程体验、评测与 Agent 对话。
- `SmartRAG_Design.md`：产品与架构设计文档。

## 目录

- [项目目标](#项目目标)
- [核心使用流程](#核心使用流程)
- [技术栈](#技术栈)
- [环境要求](#环境要求)
- [快速启动](#快速启动)
- [额外依赖安装](#额外依赖安装)
- [常用开发命令](#常用开发命令)
- [目录结构](#目录结构)
- [MCP 与 Agent 预留](#mcp-与-agent-预留)
- [English](#english)

## 项目目标

SmartRAG 的目标不是实现一条固定 RAG Pipeline，而是提供一个可视化实验平台，让用户围绕自己的材料、模型和业务问题，系统化地比较不同 RAG 策略。

核心设计原则：

- **模块可插拔**：Parser、Chunker、VectorDB、Retriever、Reranker、Filter、Compressor、Generator、Evaluator 都以注册模块的方式接入。
- **配置驱动**：每次实验都应能被配置、保存、复现、比较和导出。
- **Schema 驱动 UI**：后端模块暴露 `config_schema` 和默认配置，前端据此生成配置体验。
- **可观测优先**：任务运行会记录状态、耗时、配置、artifact、trace 和中间结果，便于后续调优。
- **Agentic 调优预留**：系统提供 MCP 与受控 action 边界，后续 Agent 可以观察运行结果、分析失败样本、提出并执行新的实验建议。

## 核心使用流程

典型使用路径如下：

1. **配置模型**
   - 进入 `配置 -> Agent管理 -> LLM管理 / Embedded管理`。
   - 添加 OpenAI Compatible、Ollama 或自定义模型连接。
   - 测试连接，确认模型可用。

2. **导入材料**
   - 进入 `配置 -> 材料管理 -> 批次管理`。
   - 创建材料批次并上传文件。
   - 材料批次会维护文件、版本和后续处理任务的关联。

3. **材料解析**
   - 进入 `构建 -> 材料解析`。
   - 选择批次，为每个文件选择 Parser，并调整 JSON 配置。
   - 运行后在 `构建 -> 解析任务` 查看状态、文本预览、元素分页和 artifact。

4. **材料分块**
   - 进入 `构建 -> 材料分块`。
   - 选择已完成的解析任务，再选择 Chunker 和分块参数。
   - 运行后在 `构建 -> 分块任务 / 分块对比` 查看 chunk 结果和对比。

5. **材料向量化**
   - 进入 `构建 -> 材料向量化`。
   - 选择已完成的分块任务、Embedding 模型和 VectorDB。
   - 默认 VectorDB 为本地 Chroma，存储在 `backend/storage/vectors/chroma`。

6. **构建 RAG 流程**
   - 进入 `构建 -> 流程构建`。
   - 选择向量索引，配置 retrieval、rerank、filter、compress、answer generator 等节点。
   - 保存后可在 `构建 -> 流程列表` 查看。

7. **流程体验**
   - 进入 `构建 -> 流程体验`。
   - 选择一个 RAG 流程，输入问题，查看每个节点的激活状态、中间输出、最终 passages 和回答。

8. **评测与报告**
   - 进入 `构建 -> 测评集生成 / 测评集任务 / 应用测评`。
   - 基于 chunk 或流程构建测评样本，运行评测并查看失败样本与指标。

9. **SmartRAG Agent**
   - 进入 `构建 -> Agent 对话`。
   - Agent 通过受控 action 与后端能力交互，用于观察任务、分析结果、辅助下一轮实验。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | React 18, Vite, TypeScript, Ant Design, TanStack Query |
| 后端 API | FastAPI, Pydantic, SQLAlchemy Async, Alembic |
| 数据库 | PostgreSQL 16 |
| 默认向量库 | Chroma persistent storage |
| 任务执行 | FastAPI background tasks，后续可替换为独立任务队列 |
| MCP | `mcp` / FastMCP，挂载在 `/mcp` |
| 包管理 | `uv` for Python, `npm` for frontend |

## 环境要求

基础环境：

- Python `>= 3.12`
- `uv`
- Node.js `>= 18`，建议 `20+`
- npm
- Docker / Docker Desktop
- PostgreSQL 16，推荐直接使用仓库内 `backend/docker-compose.yml`

默认端口：

- Backend API：`http://127.0.0.1:8000`
- API docs：`http://127.0.0.1:8000/docs`
- MCP endpoint：`http://127.0.0.1:8000/mcp`
- Frontend：`http://127.0.0.1:5173`
- Postgres：`127.0.0.1:5432`

## 快速启动

建议使用三个终端：一个启动 PostgreSQL，一个启动后端，一个启动前端。

### macOS

```bash
# Terminal 1: PostgreSQL
cd backend
cp .env.example .env
docker compose up -d postgres
```

```bash
# Terminal 2: Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Terminal 3: Frontend
cd frontend
cp .env.example .env
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

### Windows PowerShell

```powershell
# Terminal 1: PostgreSQL
cd backend
Copy-Item .env.example .env
docker compose up -d postgres
```

```powershell
# Terminal 2: Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 3: Frontend
cd frontend
Copy-Item .env.example .env
npm.cmd install
npm.cmd run dev
```

打开：

```text
http://127.0.0.1:5173
```

### Linux

```bash
# Terminal 1: PostgreSQL
cd backend
cp .env.example .env
docker compose up -d postgres
```

```bash
# Terminal 2: Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Terminal 3: Frontend
cd frontend
cp .env.example .env
npm install
npm run dev
```

打开：

```text
http://127.0.0.1:5173
```

## 环境配置

后端配置文件：

```text
backend/.env
```

常用配置项：

```env
APP_NAME=SmartRAG API
ENVIRONMENT=local
API_V1_PREFIX=/api/v1
BACKEND_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
DATABASE_URL=postgresql+asyncpg://smartrag:smartrag@127.0.0.1:5432/smartrag
SECRET_KEY=change-me-to-a-long-random-string
MATERIAL_STORAGE_ROOT=storage/materials
PARSE_ARTIFACT_ROOT=storage/parsed
CHUNK_ARTIFACT_ROOT=storage/chunks
VECTOR_STORAGE_ROOT=storage/vectors
CHROMA_ANONYMIZED_TELEMETRY=false
```

前端配置文件：

```text
frontend/.env
```

常用配置项：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

API 型 Parser 可选环境变量：

```env
LLAMA_CLOUD_API_KEY=
UPSTAGE_API_KEY=
CLOVA_OCR_API_URL=
CLOVA_OCR_SECRET_KEY=
```

## 额外依赖安装

SmartRAG 默认只安装基础后端、Chroma、本地轻量 Parser、MCP 与 Web API 所需依赖。PDF、重型解析、部分 Chunker、外部 VectorDB、Reranker、压缩器和 RAGAS 评测能力通过 `uv` extras 安装。

所有命令都在 `backend` 目录执行。

### macOS / Linux

```bash
cd backend

# PDF parser: pdfminer/pdfplumber/PyMuPDF/PyPDF/PyPDFium2
uv sync --extra parsers-pdf

# Unstructured parser
uv sync --extra parsers-unstructured

# All local non-LLM parser dependencies
uv sync --extra parsers-local

# LangChain chunkers
uv sync --extra chunk-langchain

# LlamaIndex chunkers
uv sync --extra chunk-llama-index

# Korean chunking support
uv sync --extra chunk-korean

# Semantic chunking support
uv sync --extra chunk-semantic

# Qdrant adapter
uv sync --extra vector-qdrant

# pgvector adapter
uv sync --extra vector-pgvector

# Local rerankers: FlashRank / sentence-transformers / transformers
uv sync --extra rag-rerank-local

# FlagEmbedding reranker
uv sync --extra rag-rerank-flag

# OpenVINO reranker
uv sync --extra rag-rerank-openvino

# LLMLingua compressor
uv sync --extra rag-compress

# RAGAS evaluation
uv sync --extra eval-ragas

# Most RAG runtime extras
uv sync --extra rag-all
```

### Windows PowerShell

```powershell
cd backend

# PDF parser: pdfminer/pdfplumber/PyMuPDF/PyPDF/PyPDFium2
uv sync --extra parsers-pdf

# Unstructured parser
uv sync --extra parsers-unstructured

# All local non-LLM parser dependencies
uv sync --extra parsers-local

# LangChain chunkers
uv sync --extra chunk-langchain

# LlamaIndex chunkers
uv sync --extra chunk-llama-index

# Korean chunking support
uv sync --extra chunk-korean

# Semantic chunking support
uv sync --extra chunk-semantic

# Qdrant adapter
uv sync --extra vector-qdrant

# pgvector adapter
uv sync --extra vector-pgvector

# Local rerankers: FlashRank / sentence-transformers / transformers
uv sync --extra rag-rerank-local

# FlagEmbedding reranker
uv sync --extra rag-rerank-flag

# OpenVINO reranker
uv sync --extra rag-rerank-openvino

# LLMLingua compressor
uv sync --extra rag-compress

# RAGAS evaluation
uv sync --extra eval-ragas

# Most RAG runtime extras
uv sync --extra rag-all
```

可以组合多个 extras：

```bash
uv sync --extra parsers-pdf --extra chunk-langchain --extra vector-qdrant
```

## 常用开发命令

### 后端

```bash
cd backend

# Run tests
uv run pytest -p no:cacheprovider

# Lint
uv run ruff check app tests alembic

# Apply migrations
uv run alembic upgrade head

# Check migration heads
uv run alembic heads

# Start API
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 前端

```bash
cd frontend

# Start dev server
npm run dev

# Production build
npm run build

# Preview production build
npm run preview
```

### 数据库

```bash
cd backend

# Start PostgreSQL
docker compose up -d postgres

# Stop PostgreSQL
docker compose stop postgres

# View containers
docker compose ps
```

## 目录结构

```text
SmartRAG/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes
│   │   ├── clients/        # Model provider clients
│   │   ├── core/           # Settings and security
│   │   ├── db/             # SQLAlchemy session/base
│   │   ├── models/         # ORM entities
│   │   ├── parsers/        # Parser registry and adapters
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business services
│   │   ├── main.py         # FastAPI app
│   │   └── mcp_server.py   # MCP server mount
│   ├── alembic/            # Database migrations
│   ├── prompts/            # Prompt templates
│   ├── tests/              # Backend tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/            # API client, hooks and types
│   │   ├── components/     # Shared UI components
│   │   ├── pages/          # Workspace pages
│   │   ├── App.tsx
│   │   └── styles.css
│   └── package.json
├── SmartRAG_Design.md
└── README.md
```

## MCP 与 Agent 预留

后端会在 FastAPI 应用上挂载 MCP Server：

```text
http://127.0.0.1:8000/mcp
```

MCP 当前定位是 Agent 的受控观察与操作面。它优先提供只读观察工具和资源，例如查看批次、运行状态、RAG trace、评测失败样本等；创建类工具返回 run id，由 Agent 或用户继续轮询状态。

原则：

- Agent 不直接修改数据库。
- 长任务通过后端 service layer 创建。
- 删除、覆盖、发布最佳策略等高风险动作应保留人工确认边界。
- 所有模块后续都应继续沉淀 trace、artifact、metrics 与审计信息。

---

<a id="english"></a>

# SmartRAG

> A visual workspace for RAG strategy experimentation, pipeline composition, evaluation, and future Agentic optimization.

**Language**: [中文](#smartrag) | English

SmartRAG is a UI-first RAG experimentation platform inspired by AutoRAG's modular strategy search. It turns parsing, chunking, vectorization, RAG flow design, question answering, evaluation reports, and Agent-assisted tuning into an observable and reproducible workflow.

This repository contains:

- `backend`: FastAPI backend for model management, material management, Parser/Chunker/VectorDB/RAG component registries, processing runs, evaluation, MCP Server, and SmartRAG Agent.
- `frontend`: React + Vite + Ant Design web console for configuration, build workflows, RAG experience, evaluation, and Agent chat.
- `SmartRAG_Design.md`: product and architecture design notes.

## Table of Contents

- [Goals](#goals)
- [Core Workflow](#core-workflow)
- [Tech Stack](#tech-stack)
- [Requirements](#requirements)
- [Quick Start](#quick-start)
- [Optional Dependencies](#optional-dependencies)
- [Development Commands](#development-commands)
- [Project Structure](#project-structure)
- [MCP and Agent Surface](#mcp-and-agent-surface)

## Goals

SmartRAG is not a fixed RAG pipeline. It is an experimentation platform that helps users compare RAG strategies against their own data, models, and business questions.

Core principles:

- **Pluggable modules**: Parser, Chunker, VectorDB, Retriever, Reranker, Filter, Compressor, Generator, and Evaluator are registered as replaceable modules.
- **Configuration-driven runs**: Every experiment should be configurable, saved, reproduced, compared, and exported.
- **Schema-driven UI**: Backend modules expose `config_schema` and defaults; the frontend uses them to build configuration forms.
- **Observability first**: Runs preserve status, latency, config, artifacts, traces, and intermediate outputs.
- **Agentic optimization ready**: MCP tools and controlled actions allow future Agents to observe results, analyze failures, and launch new experiments safely.

## Core Workflow

1. **Configure models**
   - Go to `Configuration -> Agent Management -> LLM / Embedding`.
   - Add OpenAI-compatible, Ollama, or custom model connections.
   - Test connection health before using them in workflows.

2. **Import materials**
   - Go to `Configuration -> Material Management -> Batches`.
   - Create a material batch and upload files.
   - Batches keep file versions and processing runs connected.

3. **Parse materials**
   - Go to `Build -> Material Parse`.
   - Select parsers and JSON configs per file.
   - Inspect progress, text previews, paginated elements, and artifacts in `Build -> Parse Runs`.

4. **Chunk materials**
   - Go to `Build -> Material Chunk`.
   - Select a completed parse run, a chunker, and chunk config.
   - Compare chunk outputs in `Build -> Chunk Runs / Chunk Compare`.

5. **Vectorize materials**
   - Go to `Build -> Material Vectorization`.
   - Select a completed chunk run, embedding model, and VectorDB.
   - The default backend is local Chroma under `backend/storage/vectors/chroma`.

6. **Build RAG flows**
   - Go to `Build -> Flow Builder`.
   - Choose a vector index and configure retrieval, rerank, filter, compression, and answer generation nodes.

7. **Try the flow**
   - Go to `Build -> Flow Experience`.
   - Ask a real question and inspect activated nodes, intermediate outputs, final passages, and final answer.

8. **Evaluate**
   - Use `Build -> Evaluation Dataset / Evaluation Runs / App Evaluation`.
   - Generate or edit samples, run evaluation, and inspect metrics and failures.

9. **Use SmartRAG Agent**
   - Go to `Build -> Agent Chat`.
   - The Agent uses controlled backend actions to observe runs, analyze outputs, and assist the next experiment.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TypeScript, Ant Design, TanStack Query |
| Backend API | FastAPI, Pydantic, SQLAlchemy Async, Alembic |
| Database | PostgreSQL 16 |
| Default VectorDB | Chroma persistent storage |
| Task execution | FastAPI background tasks, replaceable later by a dedicated queue |
| MCP | `mcp` / FastMCP mounted at `/mcp` |
| Package management | `uv` for Python, `npm` for frontend |

## Requirements

- Python `>= 3.12`
- `uv`
- Node.js `>= 18`, `20+` recommended
- npm
- Docker / Docker Desktop
- PostgreSQL 16, preferably via `backend/docker-compose.yml`

Default ports:

- Backend API: `http://127.0.0.1:8000`
- API docs: `http://127.0.0.1:8000/docs`
- MCP endpoint: `http://127.0.0.1:8000/mcp`
- Frontend: `http://127.0.0.1:5173`
- Postgres: `127.0.0.1:5432`

## Quick Start

Use three terminals: PostgreSQL, backend, and frontend.

### macOS

```bash
# Terminal 1: PostgreSQL
cd backend
cp .env.example .env
docker compose up -d postgres
```

```bash
# Terminal 2: Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Terminal 3: Frontend
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

### Windows PowerShell

```powershell
# Terminal 1: PostgreSQL
cd backend
Copy-Item .env.example .env
docker compose up -d postgres
```

```powershell
# Terminal 2: Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```powershell
# Terminal 3: Frontend
cd frontend
Copy-Item .env.example .env
npm.cmd install
npm.cmd run dev
```

Open:

```text
http://127.0.0.1:5173
```

### Linux

```bash
# Terminal 1: PostgreSQL
cd backend
cp .env.example .env
docker compose up -d postgres
```

```bash
# Terminal 2: Backend
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

```bash
# Terminal 3: Frontend
cd frontend
cp .env.example .env
npm install
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

## Configuration

Backend config:

```text
backend/.env
```

Common fields:

```env
APP_NAME=SmartRAG API
ENVIRONMENT=local
API_V1_PREFIX=/api/v1
BACKEND_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
DATABASE_URL=postgresql+asyncpg://smartrag:smartrag@127.0.0.1:5432/smartrag
SECRET_KEY=change-me-to-a-long-random-string
MATERIAL_STORAGE_ROOT=storage/materials
PARSE_ARTIFACT_ROOT=storage/parsed
CHUNK_ARTIFACT_ROOT=storage/chunks
VECTOR_STORAGE_ROOT=storage/vectors
CHROMA_ANONYMIZED_TELEMETRY=false
```

Frontend config:

```text
frontend/.env
```

Common field:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Optional cloud parser variables:

```env
LLAMA_CLOUD_API_KEY=
UPSTAGE_API_KEY=
CLOVA_OCR_API_URL=
CLOVA_OCR_SECRET_KEY=
```

## Optional Dependencies

SmartRAG installs the base backend, Chroma, lightweight parsers, MCP, and Web API dependencies by default. PDF parsing, heavy parsing, selected chunkers, external VectorDB adapters, rerankers, compressors, and RAGAS evaluation are installed via `uv` extras.

Run all commands from `backend`.

### macOS / Linux

```bash
cd backend
uv sync --extra parsers-pdf
uv sync --extra parsers-unstructured
uv sync --extra parsers-local
uv sync --extra chunk-langchain
uv sync --extra chunk-llama-index
uv sync --extra chunk-korean
uv sync --extra chunk-semantic
uv sync --extra vector-qdrant
uv sync --extra vector-pgvector
uv sync --extra rag-rerank-local
uv sync --extra rag-rerank-flag
uv sync --extra rag-rerank-openvino
uv sync --extra rag-compress
uv sync --extra eval-ragas
uv sync --extra rag-all
```

### Windows PowerShell

```powershell
cd backend
uv sync --extra parsers-pdf
uv sync --extra parsers-unstructured
uv sync --extra parsers-local
uv sync --extra chunk-langchain
uv sync --extra chunk-llama-index
uv sync --extra chunk-korean
uv sync --extra chunk-semantic
uv sync --extra vector-qdrant
uv sync --extra vector-pgvector
uv sync --extra rag-rerank-local
uv sync --extra rag-rerank-flag
uv sync --extra rag-rerank-openvino
uv sync --extra rag-compress
uv sync --extra eval-ragas
uv sync --extra rag-all
```

Extras can be combined:

```bash
uv sync --extra parsers-pdf --extra chunk-langchain --extra vector-qdrant
```

## Development Commands

### Backend

```bash
cd backend
uv run pytest -p no:cacheprovider
uv run ruff check app tests alembic
uv run alembic upgrade head
uv run alembic heads
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```bash
cd frontend
npm run dev
npm run build
npm run preview
```

### Database

```bash
cd backend
docker compose up -d postgres
docker compose stop postgres
docker compose ps
```

## Project Structure

```text
SmartRAG/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routes
│   │   ├── clients/        # Model provider clients
│   │   ├── core/           # Settings and security
│   │   ├── db/             # SQLAlchemy session/base
│   │   ├── models/         # ORM entities
│   │   ├── parsers/        # Parser registry and adapters
│   │   ├── schemas/        # Pydantic schemas
│   │   ├── services/       # Business services
│   │   ├── main.py         # FastAPI app
│   │   └── mcp_server.py   # MCP server mount
│   ├── alembic/            # Database migrations
│   ├── prompts/            # Prompt templates
│   ├── tests/              # Backend tests
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── api/            # API client, hooks and types
│   │   ├── components/     # Shared UI components
│   │   ├── pages/          # Workspace pages
│   │   ├── App.tsx
│   │   └── styles.css
│   └── package.json
├── SmartRAG_Design.md
└── README.md
```

## MCP and Agent Surface

The backend mounts an MCP Server at:

```text
http://127.0.0.1:8000/mcp
```

MCP is the controlled observation and action surface for Agents. It prioritizes read-only tools and resources for inspecting batches, run status, RAG traces, and evaluation failures. Create-style tools return a run id so Agents or users can poll progress through normal service boundaries.

Principles:

- Agents do not modify the database directly.
- Long-running work is created through the backend service layer.
- High-risk actions such as deletion, overwrite, or publishing best strategies should keep human confirmation boundaries.
- Modules should continue to emit traces, artifacts, metrics, and audit information.
