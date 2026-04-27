# SmartRAG 项目设计方案草案

## 1. 项目定位

SmartRAG 是一个面向 RAG 策略验证与自动化调优的可视化实验平台。它覆盖从原始材料解析、结构化抽取、chunk 构建、query expansion、检索、融合、重排、检索后处理、生成到评测的完整链路，让用户像搭积木一样选择模块、连接流程、配置参数、批量运行实验，并基于测评结果找到当前数据和业务场景下更优的 RAG 方案。

项目目标不是只实现一个固定 RAG pipeline，也不是只提供一个底层 SDK，而是把 AutoRAG 一类项目的模块化实验思想产品化：一方面集成主流 RAG 组件和评测框架，另一方面提供高度可用的 Web UI，让非底层框架开发者也可以清晰地配置、运行、比较和复现策略实验。

SmartRAG 的核心用户体验应该是：

```text
导入原始材料
-> 选择或推荐解析策略
-> 构建多个 corpus / chunk 版本
-> 构建或导入测评集
-> 在 UI 中拖拽或选择模块，组成候选 RAG 流程
-> 配置每个模块的参数搜索空间
-> 批量运行实验
-> 查看 leaderboard、trace、失败样本和成本
-> 导出最佳 pipeline 或进入下一轮调优
```

SmartRAG 借鉴 AutoRAG 的关键思想：

- 使用评测数据驱动 RAG 策略选择，而不是凭经验手动调参。
- 将 RAG 流程拆成有限的节点类型，每个节点下可以挂载多个模块和参数组合。
- 用配置文件描述实验空间，使实验可保存、可复现、可 diff、可导出。
- 记录 trial、summary、节点结果和最佳配置，支持后续部署。
- 支持从数据创建到优化再到部署的闭环。

SmartRAG 的差异化重点：

- **UI-first**：把复杂 YAML 和策略空间变成可视化配置、流程编排和结果分析。
- **全流程覆盖**：从原始材料解析开始，而不是只优化检索和生成。
- **积木式编排**：用户可以自由选择 parser、chunker、query processor、retriever、fusion、reranker、post processor、generator、evaluator，并连接成完整流程。
- **主流模块集成**：内置 AutoRAG 风格模块、RAGAS、DeepEval、向量库、BM25、hybrid、主流 reranker、主流 LLM/Embedding provider。
- **可观测与可解释**：每个模块、每次调用、每个样本都能追踪输入、输出、耗时、成本、指标和失败原因。
- **Agentic 调优预留**：通过埋点、artifact、MCP tools 和受控 action，为后续 Agent 分析失败样本、调整搜索空间、发起新实验提供基础。

核心能力：

- 管理原始材料和数据版本。
- 自动解析结构化、半结构化、非结构化文档。
- 生成多种 corpus/chunk/metadata 构造方案。
- 自动构建、导入或清洗测评集。
- 尝试多种 query expansion、检索、融合、重排、检索后处理和生成策略。
- 支持多评测框架接入，例如 AutoRAG-style IR 指标、RAGAS、DeepEval、自定义业务指标。
- 输出可解释的最佳 RAG 策略和可部署 pipeline。
- 通过 Web UI 展示实验空间、执行状态、指标、失败样本、trace 和策略演进过程。

## 2. 架构原则与技术路线

SmartRAG 的首要架构目标是高灵活性、低耦合和可长期扩展。系统不能把某一种 parser、chunker、retriever、reranker、LLM、评测框架或优化算法写死在主流程里，而应该把这些能力都抽象成可注册、可替换、可观测、可被 Agent 调用的模块。

### 2.1 核心架构原则

1. **策略即插件**

   所有可变能力都以插件形式存在，包括：

   - 文档解析器。
   - chunker。
   - metadata extractor。
   - embedding_text builder。
   - query transformer。
   - retriever。
   - fusion strategy。
   - reranker。
   - passage filter。
   - passage compressor。
   - prompt maker。
   - generator。
   - evaluator。
   - optimizer。
   - agent tool。

   主流程只依赖统一接口，不依赖具体实现。

2. **配置驱动执行**

   每一次 RAG 实验都应该能被完整表达为一份配置：

   ```yaml
   parser:
     type: pymupdf
   chunker:
     type: section_aware
   retriever:
     type: hybrid_rrf
   reranker:
     type: bge
   evaluator:
     - type: ir
     - type: ragas
   ```

   配置必须可保存、可复现、可 diff、可导出。

3. **节点、模块、参数空间分离**

   SmartRAG 的实验配置需要区分三层概念：

   - `Node`：流程中的能力节点，例如 parse、chunk、query_expansion、retrieval、rerank、post_process、generate、evaluate。
   - `Module`：节点下的具体实现，例如 bm25、vectordb、hybrid_rrf、bge_reranker、ragas_evaluator。
   - `Search Space`：模块参数的候选集合，例如 chunk_size、overlap、top_k、hybrid weight、rerank top_k、prompt template。

   UI 负责把这些概念变成可视化积木和表单；后端负责把用户选择编译成可执行实验配置。

4. **数据对象稳定，模块实现可变**

   系统内部核心数据结构需要稳定，例如：

   ```text
   Document
   ParsedDocument
   Chunk
   CorpusVersion
   EvalSample
   RagConfig
   RagRun
   TraceEvent
   EvaluationResult
   ```

   模块之间通过这些标准对象交互，避免直接互相调用内部实现。

5. **模块之间只通过契约交互**

   每个模块必须声明：

   - `input_schema`
   - `output_schema`
   - `config_schema`
   - `capabilities`
   - `required_resources`
   - `cost_model`
   - `observability_hooks`

   这样才能让 UI、优化器和 Agent 在不知道具体实现的情况下编排模块。

6. **UI 配置能力由 schema 驱动**

   每个模块的配置项、默认值、校验规则、枚举选项、参数搜索范围、UI 控件类型都应由 `config_schema` 或独立 `ui_schema` 描述。这样新增模块时，UI 不需要为每个模块手写专用页面。

7. **实验优先，生产兼容**

   SmartRAG 的核心是实验系统。所有策略都应该先能作为实验配置运行，然后再导出为生产 pipeline。

   ```text
   Experiment Config
     -> Run
     -> Evaluate
     -> Compare
     -> Export Best Pipeline
   ```

8. **可观测性是基础能力，不是附加功能**

   每个模块调用都必须产生日志、指标和 trace。Agent 后续要能读取这些观测数据，分析失败原因并提出下一轮策略。

9. **Agent 不直接绕过系统边界**

   Agent 只能通过受控工具调用系统能力，例如 MCP tools、内部 command bus、evaluation API。不能直接修改数据库或绕过实验编排器。

### 2.2 分层技术路线

建议采用以下分层：

```text
UI / API Layer
  -> Orchestration Layer
  -> Plugin Runtime
  -> RAG Module Layer
  -> Evaluation Layer
  -> Observability Layer
  -> Storage Layer
  -> Agent & MCP Layer
```

各层职责：

| 层 | 职责 |
|---|---|
| UI / API Layer | 项目管理、文件上传、实验配置、结果展示 |
| Orchestration Layer | 编排实验 DAG、管理运行状态、失败重试 |
| Plugin Runtime | 注册、加载、校验、隔离可插拔模块 |
| RAG Module Layer | parser、chunker、retriever、reranker、generator 等具体能力 |
| Evaluation Layer | 统一接入 IR、RAGAS、DeepEval、自定义指标 |
| Observability Layer | 日志、trace、metrics、artifact、agent observation |
| Storage Layer | 原始材料、corpus、向量索引、实验结果、trace |
| Agent & MCP Layer | 提供 Agent 可调用工具、暴露系统状态和可执行动作 |

### 2.3 插件系统要求

插件需要支持三类形态：

1. **内置插件**

   随系统发布，稳定维护。例如 BM25、dense retrieval、RRF、基础 chunker、RAGAS adapter。

2. **用户自定义插件**

   用户可以通过 Python class、HTTP service 或 MCP server 接入自己的策略。

3. **Agent 生成插件**

   后续允许 Agent 基于失败样本生成候选策略，但必须经过 sandbox、schema 校验和人工确认后才能进入正式实验。

插件注册信息示例：

```json
{
  "plugin_id": "retriever.hybrid_rrf",
  "module_type": "retriever",
  "display_name": "Hybrid RRF Retriever",
  "input_schema": "RetrievalRequest",
  "output_schema": "RetrievalResult",
  "config_schema": {
    "bm25_weight": "float",
    "dense_weight": "float",
    "top_k": "int"
  },
  "capabilities": ["keyword", "dense", "fusion"],
  "supports_streaming": false,
  "supports_batch": true
}
```

插件最小接口：

```python
class SmartRAGPlugin:
    plugin_id: str
    module_type: str

    def config_schema(self) -> dict:
        ...

    def input_schema(self) -> dict:
        ...

    def output_schema(self) -> dict:
        ...

    def run(self, input_data, config, context):
        ...
```

### 2.4 编排模型

RAG 实验不应该写成固定链路，而应该是 DAG。

示例：

```text
Parse
  -> Build Corpus A
  -> Build Corpus B
  -> Build Eval Set
  -> Run Retrieval Configs
  -> Run Rerank Configs
  -> Run Generation Configs
  -> Evaluate
  -> Select Best
```

每个 DAG node 都需要：

- 输入 artifact。
- 输出 artifact。
- module config。
- run status。
- trace id。
- cost。
- latency。
- error。
- retry policy。

实验编排器需要支持：

- 串行执行。
- 并行执行。
- 批量执行。
- 失败跳过。
- 断点续跑。
- 缓存命中。
- 同配置去重。
- artifact 复用。

### 2.5 观测与埋点要求

系统需要从第一天内置 observability。

每次模块调用至少记录：

```json
{
  "trace_id": "trace_001",
  "run_id": "run_001",
  "node_id": "retrieval_003",
  "module_type": "retriever",
  "plugin_id": "retriever.hybrid_rrf",
  "config_hash": "sha256...",
  "input_artifact_ids": ["artifact_001"],
  "output_artifact_ids": ["artifact_002"],
  "started_at": "2026-04-27T16:00:00+08:00",
  "ended_at": "2026-04-27T16:00:02+08:00",
  "latency_ms": 2000,
  "token_usage": 1200,
  "cost": 0.01,
  "status": "success",
  "error": null
}
```

埋点类型：

- **Structured logs**：面向调试和审计。
- **Metrics**：面向看板和优化，例如 latency、cost、recall、faithfulness。
- **Traces**：面向链路分析和 Agent 诊断。
- **Artifacts**：保存中间产物，例如 parsed document、corpus、retrieved contexts、LLM prompt、LLM answer。
- **Events**：关键业务事件，例如 experiment_started、best_config_selected、agent_suggestion_created。

需要重点保留的 RAG trace：

- 原始 query。
- query rewrite / decomposition 结果。
- metadata filter。
- 每路 retriever 的候选结果。
- fusion 前后排序。
- reranker 分数。
- filter/compressor 前后文本。
- final prompt。
- final answer。
- citation。
- evaluator 输入和输出。

### 2.6 Agent 观测与控制面

Agentic AutoRAG 的能力不应该直接嵌死在主流程里，而应该作为一个可选控制面。

Agent 可观察：

- 项目文档类型分布。
- parser 输出质量。
- chunk 长度分布。
- metadata 完整度。
- 检索失败样本。
- 生成失败样本。
- 指标趋势。
- 实验成本。
- 当前搜索空间。
- 历史最佳配置。

Agent 可执行：

- 生成候选 metadata schema。
- 生成候选 chunk 策略。
- 推荐 query transform。
- 推荐 evaluator 组合。
- 分析失败样本。
- 扩展或收缩搜索空间。
- 发起新实验。
- 生成实验报告。

Agent 不应直接执行：

- 删除原始材料。
- 覆盖历史实验。
- 修改已发布最佳策略。
- 绕过 evaluator 标记配置为最佳。

这些高风险动作需要人工确认或权限策略。

### 2.7 MCP 支持要求

SmartRAG 应预留 MCP server，使外部 Agent 能通过标准工具协议操作系统。

第一批 MCP tools：

```text
list_projects
get_project_summary
list_data_sources
inspect_document_structure
list_corpus_versions
inspect_chunk
list_eval_datasets
run_experiment
get_run_status
get_run_trace
get_leaderboard
get_failure_cases
create_strategy_proposal
approve_strategy_proposal
export_best_pipeline
```

MCP resources：

```text
smartrag://projects/{project_id}/summary
smartrag://runs/{run_id}/trace
smartrag://runs/{run_id}/leaderboard
smartrag://datasets/{dataset_id}/samples
smartrag://corpus/{corpus_version_id}/chunks
```

MCP 设计约束：

- 所有工具必须有明确 schema。
- 所有写操作必须记录审计日志。
- 高风险操作必须要求 confirmation。
- Agent 只能拿到当前权限允许的数据。
- 长任务返回 run id，不阻塞工具调用。

### 2.8 切面与 Hook 机制

系统需要支持横切能力，避免在每个模块里重复写逻辑。

建议提供 hook points：

```text
before_module_run
after_module_run
on_module_error
before_llm_call
after_llm_call
before_retrieval
after_retrieval
before_evaluation
after_evaluation
before_agent_action
after_agent_action
```

可通过 hook 实现：

- 日志记录。
- 成本统计。
- token 统计。
- prompt/response 保存。
- PII 脱敏。
- 权限检查。
- 缓存。
- 限流。
- 熔断。
- 自动重试。
- Agent observation event 生成。

### 2.9 可扩展评测层

评测层必须是 adapter 架构，而不是固定依赖某一个框架。

每个 evaluator adapter 声明：

```text
required_fields
produced_metrics
cost_level
latency_level
requires_llm
requires_reference_answer
requires_reference_context
```

示例：

```json
{
  "adapter": "ragas",
  "required_fields": ["query", "answer", "retrieved_contexts", "reference_answer"],
  "produced_metrics": ["faithfulness", "answer_relevancy", "context_precision"],
  "requires_llm": true
}
```

优化器只消费统一后的 `EvaluationResult`，不直接依赖 RAGAS、DeepEval 或 AutoRAG 指标实现。

### 2.10 技术选型方向

初步建议：

| 能力 | 技术方向 |
|---|---|
| 后端 API | Python FastAPI |
| 异步任务 | Celery / Dramatiq / Arq，MVP 可先用后台任务 |
| 实验编排 | 自研轻量 DAG runner，后续可接 Temporal / Prefect |
| 插件运行时 | Python entrypoints + config registry |
| 数据校验 | Pydantic |
| 数据库 | PostgreSQL，MVP 可 SQLite |
| 向量库 | Qdrant 或 Chroma |
| 对象存储 | 本地文件，后续 S3/MinIO |
| 日志 | structlog / loguru + JSON logs |
| Trace | OpenTelemetry |
| Metrics | Prometheus format，MVP 可落库 |
| 前端 | React / Next.js |
| UI 国际化 | i18next / next-intl，语言包 JSON 管理 |
| MCP | 独立 MCP server，与后端 API 共用 service layer |
| Agent | 可选内置 Agent，不影响核心 pipeline |

### 2.11 第一阶段架构落地边界

MVP 不需要一次性实现完整插件市场和复杂 Agent，但需要把接口预留好。

第一阶段必须具备：

- 模块 registry。
- 统一 config schema。
- 统一 run trace。
- 统一 artifact 存储。
- 统一 evaluation result。
- 基础 hook 机制。
- 基础 MCP tool skeleton。
- Web UI 能查看实验、trace、leaderboard。

可以暂缓：

- 多租户权限。
- 插件热加载。
- Agent 自动写插件。
- 复杂工作流引擎。
- 分布式执行。
- 完整 OpenTelemetry 后端。

## 3. 总体架构

SmartRAG 的总体架构围绕“项目、材料、产物、实验、评测、导出”组织。前端提供面向用户的流程工作台，后端提供可复用的实验编排与插件运行时。所有模块都通过统一 artifact 和 trace 交互，避免 UI、优化器、Agent 或具体插件彼此强耦合。

```text
Raw Material Manager
  -> Parser & Extractor
  -> Corpus Builder
  -> Evaluation Dataset Builder
  -> Query Processor
  -> Retrieval Engine
  -> Post-Retrieval Processor
  -> Generator
  -> Evaluator
  -> Optimizer / Agent
  -> Web UI & Experiment Console
```

从用户视角，系统是一条可配置流水线；从后端视角，系统是一个 artifact 驱动的实验 DAG。

```text
Project
  -> Material Batch
  -> Parsed Artifact
  -> Corpus Version
  -> Eval Dataset
  -> Experiment Graph
  -> Trial / Run
  -> Evaluation Result
  -> Best Strategy
  -> Exported Pipeline
```

系统内部建议使用统一的数据对象：

```text
Document
ParsedDocument
Chunk
CorpusVersion
EvalSample
RagConfig
RagRun
TraceEvent
Artifact
EvaluationResult
BestStrategy
```

核心模块边界：

| 模块 | 主要职责 | 典型产物 |
|---|---|---|
| Material Manager | 原始文件、批次、版本、来源管理 | `Document`、`MaterialBatch` |
| Parser & Extractor | 多格式解析、结构化元素抽取、metadata 抽取 | `ParsedDocument` |
| Corpus Builder | chunk、embedding_text、metadata schema、索引准备 | `CorpusVersion`、`Chunk` |
| Eval Dataset Builder | 合成 QA、导入标注、清洗测评样本 | `EvalDataset`、`EvalSample` |
| Pipeline Designer | 在 UI 中配置节点、模块和搜索空间 | `ExperimentGraph`、`RagConfig` |
| Orchestrator | 执行 DAG、复用 artifact、记录状态 | `RagRun`、`TraceEvent` |
| Evaluator | 统一运行 IR、RAGAS、DeepEval、自定义指标 | `EvaluationResult` |
| Optimizer | 根据目标函数选择最佳组合并推荐下一轮实验 | `BestStrategy`、`StrategyProposal` |
| Exporter | 导出 YAML/JSON、可运行 pipeline、API 服务配置 | `PipelineBundle` |

第一阶段可以先实现线性流程和有限分支，但数据模型需要允许后续扩展为更复杂的 DAG，包括多路检索、分支评测、节点级缓存、节点级最优选择和 Agent 自动扩展搜索空间。

## 4. 功能一：LLM、Embedding 与 Agent 配置管理

SmartRAG 会在多个环节使用 AI 模型，包括 query expansion、query rewrite、query compression、query decomposition、HyDE、metadata extraction、LLM-as-judge、answer generation、multimodal parsing、reranking 和 Agent 决策。因此需要先建立一个统一、可扩展的模型管理与 Agent 配置中心。

本功能分为两层：

```text
Model Registry
  -> 管理基础模型连接信息、能力、健康状态

Agent Profile Registry
  -> 基于已注册模型配置专用 Agent、prompt 和用途
```

### 4.1 基础模型管理

基础模型管理用于保存所有可调用模型的接入信息。UI 上建议分成不同分类，但底层用统一 schema 支持后续扩展。

第一批模型分类：

- `llm`：普通文本生成模型。
- `embedding`：文本 embedding 模型。
- `reranker`：重排模型。
- `multimodal`：多模态模型，例如图片/PDF 页面理解。
- `reasoning`：推理模型。
- `moe`：MoE 或路由型模型。
- `vision_embedding`：图片或页面 embedding 模型。
- `speech`：语音识别或语音理解模型。
- `custom`：用户自定义模型服务。

UI 基础字段：

| 字段 | 说明 |
|---|---|
| `display_name` | 用户自定义显示名称，必须唯一 |
| `model_category` | 模型分类，例如 `llm`、`embedding` |
| `provider` | OpenAI、Azure OpenAI、Ollama、vLLM、DashScope、DeepSeek、自定义等 |
| `base_url` | OpenAI-compatible endpoint 或自定义服务 URL |
| `model_name` | 实际调用的模型名 |
| `api_key` | 密钥，必须加密存储 |
| `api_version` | 可选，用于 Azure 或自定义服务 |
| `timeout_seconds` | 调用超时时间 |
| `max_retries` | 最大重试次数 |
| `enabled` | 是否启用 |

系统探测后补充字段：

| 字段 | 说明 |
|---|---|
| `connection_status` | `unknown`、`checking`、`available`、`failed` |
| `last_check_at` | 最近一次探测时间 |
| `last_error` | 最近一次失败原因 |
| `resolved_model_name` | 服务实际返回的模型名 |
| `context_window` | 上下文长度 |
| `max_output_tokens` | 最大输出 token |
| `embedding_dimension` | embedding 维度，仅 embedding 模型需要 |
| `supports_streaming` | 是否支持流式输出 |
| `supports_json_schema` | 是否支持 structured output |
| `supports_tools` | 是否支持 tool/function calling |
| `supports_vision` | 是否支持图像输入 |
| `supports_batch` | 是否支持批量请求 |
| `model_traits` | 能力标签，例如 `reasoning`、`fast`、`cheap`、`long_context`、`multilingual` |
| `pricing` | 可选，输入/输出 token 或 embedding 成本 |

模型配置示例：

```json
{
  "model_id": "model_001",
  "display_name": "gpt-4o-mini-prod",
  "model_category": "llm",
  "provider": "openai_compatible",
  "base_url": "https://api.example.com/v1",
  "model_name": "gpt-4o-mini",
  "api_key_ref": "secret:model_001_api_key",
  "connection_status": "available",
  "context_window": 128000,
  "max_output_tokens": 16384,
  "supports_streaming": true,
  "supports_json_schema": true,
  "supports_tools": true,
  "model_traits": ["fast", "cheap", "multilingual"]
}
```

### 4.2 模型连通性与能力探测

用户保存模型后，系统需要自动发起一次健康检查。

LLM 探测：

- 调用最小 prompt，例如 `Reply with OK.`。
- 校验是否返回正常文本。
- 如果支持 streaming，测试流式接口。
- 如果声称支持 JSON schema，测试 structured output。
- 如果声称支持 tool calling，测试一个无副作用 dummy tool。
- 记录延迟、错误、返回 token usage。

Embedding 探测：

- 用固定文本调用 embedding。
- 记录 embedding 维度。
- 校验维度是否稳定。
- 校验 batch embedding 是否可用。
- 记录平均延迟。

Reranker 探测：

- 输入一条 query 和两段候选文本。
- 校验是否返回 score 或排序。
- 记录 score 范围和排序方向。

能力探测需要分为两类：

```text
declared_capability: 用户或 provider 声明的能力
verified_capability: 系统实际测试通过的能力
```

后续策略选择只能默认使用 `verified_capability`。

### 4.3 模型密钥与安全要求

模型密钥不能明文出现在：

- 数据库普通字段。
- 实验配置导出文件。
- trace。
- 日志。
- Web UI 响应。
- Agent observation。
- MCP resource。

推荐做法：

- `api_key` 加密存储，业务表只保存 `api_key_ref`。
- 后端执行调用时临时解密。
- trace 中只记录 `model_id` 和 `display_name`。
- UI 只展示 masked key，例如 `sk-****abcd`。
- Agent 默认不可读取密钥，只能通过受控 model invocation tool 调用模型。

### 4.4 模型用途与默认模型

项目级别需要允许配置默认模型：

| 用途 | 默认模型类型 |
|---|---|
| `default_generation_llm` | 普通回答生成 |
| `default_reasoning_llm` | 复杂策略分析 |
| `default_fast_llm` | query rewrite、分类、轻量任务 |
| `default_judge_llm` | LLM-as-judge |
| `default_embedding_model` | 文本向量 |
| `default_reranker` | 检索后重排 |
| `default_multimodal_model` | 图片/PDF 页面理解 |

模型用途不直接绑定具体业务模块，而是作为 fallback。具体策略可以覆盖默认模型。

### 4.5 专用 Agent 配置

query expansion、HyDE、query decomposition、metadata extraction、失败样本分析等能力都可以被视为专用 Agent Profile。

Agent Profile 是对基础模型的二次封装：

```text
Agent Profile = selected model + prompt template + runtime parameters + output schema + usage scope
```

UI 需要在模型管理旁边提供 Agent 配置列或独立 tab。

用户配置流程：

1. 从已注册成功的 LLM 中选择一个模型。
2. 选择 Agent 类型。
3. 系统加载默认 `prompt.md`。
4. 用户可编辑 prompt。
5. 用户填写唯一 Agent 名称。
6. 系统测试 Agent 输出是否符合 schema。
7. 保存为可复用 Agent Profile。

第一批 Agent 类型：

| Agent 类型 | 用途 |
|---|---|
| `query_rewrite` | 把长问题或口语问题改写成检索友好问题 |
| `query_compress` | 压缩超长问题，保留检索意图 |
| `multi_query` | 生成多个同义检索 query |
| `query_decompose` | 拆分多跳或多意图问题 |
| `hyde` | 生成假想答案/假想文档用于检索 |
| `metadata_extraction` | 从 query 中抽取日期、作者、章节、服务名等 filter |
| `routing` | 判断使用哪种检索策略 |
| `failure_analysis` | 分析失败样本并提出下一轮实验建议 |
| `strategy_planner` | 根据数据类型生成候选策略空间 |
| `llm_judge` | 作为评测裁判 |

Agent Profile 示例：

```json
{
  "agent_id": "agent_001",
  "agent_name": "ops-log-query-decomposer",
  "agent_type": "query_decompose",
  "model_id": "model_001",
  "prompt_template_path": "prompts/query_decompose/default.md",
  "prompt_template": "...",
  "output_schema": {
    "semantic_queries": "list[str]",
    "metadata_filter": "dict"
  },
  "temperature": 0.0,
  "max_output_tokens": 2048,
  "enabled": true,
  "version": 1
}
```

名称约束：

- `agent_name` 在同一项目内必须唯一。
- Agent 修改 prompt 后自动生成新版本。
- 历史实验绑定具体 `agent_id + version`，不能被后续修改影响。

### 4.6 默认 Prompt 文件

每种 Agent 类型都应有默认 `prompt.md`。

建议目录：

```text
prompts/
  query_rewrite/default.md
  query_compress/default.md
  multi_query/default.md
  query_decompose/default.md
  hyde/default.md
  metadata_extraction/default.md
  routing/default.md
  failure_analysis/default.md
  strategy_planner/default.md
  llm_judge/default.md
```

Prompt 文件要求：

- 使用 markdown 保存，方便 UI 编辑。
- 支持变量占位符，例如 `{query}`、`{chat_history}`、`{document_type}`、`{metadata_schema}`。
- 声明期望输出格式。
- 对需要结构化输出的 Agent，必须配套 JSON schema。
- 每次 prompt 修改都要生成版本。

### 4.7 Agent 连通性测试

保存 Agent Profile 后，需要执行一次 dry-run。

不同 Agent 使用不同测试输入：

```json
{
  "query_rewrite": "我想找一下昨天那个 redis 连接数暴涨的问题，后来到底咋解决的？",
  "query_decompose": "4月26日 Redis 为什么出问题，怎么恢复的，有没有影响订单？",
  "hyde": "为什么 Redis 连接数会突然上涨？",
  "metadata_extraction": "看一下 2026-04-26 订单服务的 5xx 问题"
}
```

测试通过条件：

- 模型调用成功。
- 输出符合 schema。
- 输出长度在合理范围内。
- 如果配置了 JSON 输出，必须能被解析。
- trace 中记录 prompt version、model_id、latency、token usage。

### 4.8 UI 页面设计

模型管理 UI 建议分成两个区域。

左侧：基础模型列表。

展示字段：

- 名称。
- 类型。
- provider。
- model name。
- 连接状态。
- context window。
- embedding dimension。
- 支持能力标签。
- 最近检查时间。
- 默认用途标记。

右侧：选中模型详情。

支持操作：

- 新增模型。
- 编辑模型。
- 测试连接。
- 查看能力探测结果。
- 设置项目默认模型。
- 禁用模型。
- 删除未被实验引用的模型。

Agent 配置 UI：

- Agent 名称。
- Agent 类型。
- 选择基础 LLM。
- 选择或编辑默认 prompt.md。
- 输出 schema 预览。
- dry-run 测试。
- 保存版本。
- 查看历史版本。
- 查看在哪些实验中被使用。

### 4.9 与实验系统的关系

RAG 实验配置不直接保存模型密钥或 prompt 全文，而是引用版本化对象：

```yaml
query_processor:
  type: query_decompose
  agent_profile_ref:
    agent_id: agent_001
    version: 3

embedding:
  model_id: model_embed_001

generator:
  model_id: model_llm_002
  prompt_template_id: answer_prompt_001
```

这样可以保证：

- 实验可复现。
- prompt 修改不会污染历史结果。
- 模型配置变更可追踪。
- Agent 后续能基于历史配置做对比分析。

### 4.10 MCP 与 Agent 工具预留

模型管理需要暴露 MCP tools，供内置或外部 Agent 查询可用能力。

第一批工具：

```text
list_models
get_model_detail
test_model_connection
list_agent_profiles
get_agent_profile
test_agent_profile
create_agent_profile_proposal
```

写操作建议采用 proposal 模式：

```text
Agent 创建建议
-> 用户确认
-> 系统保存
```

Agent 可以读取：

- 已启用模型列表。
- 模型能力标签。
- Agent Profile 列表。
- Agent dry-run 结果。
- 历史实验中某个 Agent 的表现。

Agent 不可读取：

- 明文 API key。
- 未授权项目的模型配置。
- 被禁用模型的密钥信息。

### 4.11 数据表初稿

核心表：

```text
model_providers
model_connections
model_capabilities
model_health_checks
agent_profiles
agent_profile_versions
prompt_templates
prompt_template_versions
model_usage_events
```

`model_connections` 关键字段：

```text
model_id
project_id
display_name
model_category
provider
base_url
model_name
api_key_ref
enabled
connection_status
last_check_at
created_at
updated_at
```

`agent_profile_versions` 关键字段：

```text
agent_id
version
agent_name
agent_type
model_id
prompt_template
output_schema
runtime_config
created_at
created_by
```

### 4.12 第一阶段范围

MVP 阶段必须支持：

- OpenAI-compatible LLM 接入。
- OpenAI-compatible embedding 接入。
- Ollama 本地模型接入。
- 模型连通性测试。
- context window、embedding dimension、streaming、JSON 输出能力记录。
- query rewrite、multi-query、query decomposition、HyDE、metadata extraction 五类 Agent Profile。
- 每类 Agent 一个默认 prompt.md。
- Agent dry-run。
- 实验配置引用 `model_id` 和 `agent_id + version`。

MVP 暂缓：

- 多模态模型完整能力探测。
- MoE 内部路由可视化。
- 自动价格抓取。
- Agent 自动生成新插件。
- 企业级密钥托管集成。

## 5. 功能二：原始材料批次管理

原始材料管理负责保存用户上传或接入的数据源，并以“批次”为基本组织单位管理后续解析、chunk、embedding、测试集、问答集、质量报告和实验结果。

核心原则：

- 用户一次上传的一组文件形成一个材料批次。
- 批次由用户命名，系统分配全局唯一 `batch_id`。
- 文件在批次内可以单独新增或删除。
- 原始文件不允许在线编辑，只允许新增、删除和重新上传新文件。
- 每次批次内容变化都要形成可追溯版本。
- 后续所有解析、embedding、测试集和质量报告都绑定到具体批次版本。

### 5.1 批次概念

批次是 SmartRAG 的数据组织边界。

```text
MaterialBatch
  -> MaterialBatchVersion
  -> MaterialFile
  -> ParseRun
  -> CorpusVersion
  -> EvalDataset
  -> QualityReport
  -> RagExperiment
```

批次示例：

```json
{
  "batch_id": "batch_001",
  "batch_name": "2026-04 运维日志与故障复盘",
  "description": "Redis、订单服务、支付服务相关运维记录",
  "current_version": 3,
  "file_count": 128,
  "created_by": "user_001",
  "created_at": "2026-04-27T16:00:00+08:00",
  "updated_at": "2026-04-27T17:00:00+08:00"
}
```

批次名称要求：

- 同一项目内 `batch_name` 建议唯一。
- `batch_id` 必须全局唯一，作为系统内部引用。
- 后续 UI 可以允许批次改名，但改名不影响 `batch_id` 和历史实验。

### 5.2 批次内文件管理

支持上传方式：

- 多文件批量上传。
- 文件夹上传。
- 拖拽上传。
- 压缩包上传后解包。
- 后续扩展 URL、Confluence、Jira、对象存储、Git 仓库。

支持文件类型：

- PDF、Word、Excel、Markdown、HTML、TXT、CSV、JSON。
- 后续扩展图片、音频、视频、日志包、数据库导出。

文件记录示例：

```json
{
  "file_id": "file_001",
  "batch_id": "batch_001",
  "original_filename": "redis_incident_20260426.pdf",
  "file_ext": ".pdf",
  "mime_type": "application/pdf",
  "size_bytes": 1024000,
  "checksum": "sha256...",
  "storage_uri": "object://material/batch_001/file_001",
  "status": "active",
  "created_at": "2026-04-27T16:10:00+08:00"
}
```

文件约束：

- 不允许修改文件内容。
- 删除文件采用逻辑删除，保留历史版本追溯。
- 同名文件允许上传，但必须有不同 `file_id`。
- 相同 checksum 的重复文件可以提示用户，但不强制禁止。
- 历史实验引用的文件不能物理删除。

### 5.3 批次版本管理目标

批次版本用于回答这些问题：

```text
某一次解析基于哪些文件？
某一次 embedding 是否只需要增量处理新增文件？
某个测试集是基于哪个批次版本生成的？
某个质量报告对应哪些原始材料？
删除文件后，旧实验还能不能复现？
```

每个版本至少记录：

```json
{
  "batch_version_id": "batch_001_v003",
  "batch_id": "batch_001",
  "version_number": 3,
  "change_type": "add_files",
  "parent_version_id": "batch_001_v002",
  "added_file_ids": ["file_120", "file_121"],
  "removed_file_ids": [],
  "active_file_ids_snapshot": ["file_001", "file_002", "file_120", "file_121"],
  "created_at": "2026-04-27T17:00:00+08:00",
  "created_by": "user_001"
}
```

版本必须服务于增量处理：

- 新增文件后，只解析新增文件。
- 删除文件后，新的 corpus version 排除被删文件。
- 未变更文件的解析结果、chunk、embedding 可以复用。
- 质量报告要明确覆盖的 batch version。

### 5.4 批次版本管理可选方案

这里先给出几个可行方案，后续需要选择一种作为主方案。

#### 方案 A：快照版本表

每次批次变化时，保存当前 active file id 的完整快照。

```text
batch_versions
  version_number
  active_file_ids_snapshot
```

优点：

- 实现简单。
- 查询某个版本包含哪些文件非常快。
- 回溯历史版本直观。
- 适合 MVP。

缺点：

- 文件数量很大时，快照字段会变大。
- 版本之间重复存储 active file id。

适用场景：

- 初期批次数量和文件规模中等。
- 更重视实现速度和可理解性。

#### 方案 B：事件溯源 Event Sourcing

只记录事件，不保存完整快照。

```text
batch_events
  event_type: batch_created | file_added | file_removed
  file_id
  event_time
```

某个版本的文件集合由事件重放得到。

优点：

- 历史变化过程最完整。
- 存储更节省。
- 很适合审计和 Agent 分析变化。

缺点：

- 查询某个版本需要重放事件，复杂度更高。
- 需要定期生成 checkpoint，否则历史长了会慢。
- MVP 实现成本高于快照方案。

适用场景：

- 强审计需求。
- 未来会有复杂增量同步、外部数据源同步。

#### 方案 C：Manifest 文件版本

每个批次版本生成一个 manifest 文件，内容是当前文件清单和 checksum。

```text
manifests/
  batch_001/
    v001.json
    v002.json
    v003.json
```

数据库只保存 manifest URI 和版本元信息。

优点：

- 适合对象存储。
- manifest 可以直接作为后续解析、embedding 的输入。
- 易于导出、备份和复现实验。

缺点：

- 需要处理 manifest 文件和数据库一致性。
- 查询单个文件历史时不如数据库表方便。

适用场景：

- 后续计划接 S3/MinIO。
- 重视实验可复现和 artifact 化。

#### 方案 D：Git-like 内容寻址

文件按 checksum 内容寻址，批次版本类似 commit。

```text
blob: file content by checksum
tree: file list
commit: batch version
```

优点：

- 去重能力强。
- 可复现性最好。
- 适合大规模文件和跨批次复用。

缺点：

- 实现复杂。
- 用户理解成本较高。
- 初期容易过度设计。

适用场景：

- 长期需要企业级数据版本管理。
- 大量重复材料、多项目共享材料。

#### 初步建议

MVP 推荐在 **方案 A：快照版本表** 和 **方案 C：Manifest 文件版本** 中选择。

较务实的折中是：

```text
数据库保存版本元信息和 active file id 快照
同时生成 manifest artifact 供实验复现
```

也就是：

```text
短期查询靠数据库快照
长期复现靠 manifest 文件
```

### 5.5 批次关联产物

后续所有数据产物都必须绑定 `batch_id` 和 `batch_version_id`。

| 产物 | 绑定粒度 |
|---|---|
| ParseRun | `batch_version_id` + parser config |
| ParsedDocument | `file_id` + parser config hash |
| CorpusVersion | `batch_version_id` + chunk config + metadata strategy |
| EmbeddingIndex | `corpus_version_id` + embedding model |
| EvalDataset | `batch_version_id` 或 `corpus_version_id` |
| QA Dataset | `eval_dataset_id` |
| QualityReport | `batch_version_id`、`corpus_version_id` 或 `run_id` |
| RagExperiment | `batch_version_id` + `corpus_version_id` + config |

这样才能支持：

- 同一批材料不同解析策略对比。
- 同一批材料不同 chunk 策略对比。
- 新增文件后的增量解析和增量 embedding。
- 删除文件后的新版本实验。
- 历史实验可复现。

### 5.6 增量处理策略

增量处理依赖 checksum、file_id、config hash 和 batch version。

判断是否可复用：

```text
same file checksum
+ same parser config hash
= parsed result reusable

same parsed document hash
+ same chunk config hash
+ same metadata strategy hash
= chunks reusable

same chunk content hash
+ same embedding model id
= embedding reusable
```

新增文件流程：

```text
add files
-> create new batch version
-> parse only new files
-> chunk new parsed documents
-> embed new chunks
-> merge with previous reusable index
```

删除文件流程：

```text
remove file logically
-> create new batch version
-> create new corpus version excluding removed file
-> vector index marks removed file chunks inactive
-> old versions remain reproducible
```

### 5.7 解析工具注册与归一化架构

原始材料管理不仅负责文件上传，也需要为后续解析阶段提供统一的工具发现、工具描述、配置 schema 和归一化输出能力。

后台代码应采用：

```text
Parser Strategy
  -> Parser Adapter
  -> Normalized Parsed Output
```

其中：

- `Parser Strategy` 负责声明解析工具能力和执行入口。
- `Parser Adapter` 负责调用具体第三方解析工具，并把不同工具的原始输出归一化。
- `Normalized Parsed Output` 是 SmartRAG 内部稳定数据结构，供 chunk、metadata、质量评估和 Agent 使用。

#### 5.7.1 统一归一化输出格式

不同解析工具原生输出差异很大，例如 LlamaParse 可能输出 Markdown，PDFPlumber 可能输出 page、bbox、table，OCR 工具可能输出文本块和坐标。SmartRAG 不应直接把这些原生格式暴露给后续模块，而应该先归一化成统一结构。

建议归一化输出：

```json
{
  "parsed_document_id": "parsed_doc_001",
  "file_id": "file_001",
  "batch_id": "batch_001",
  "batch_version_id": "batch_001_v003",
  "parser_name": "llama_parse",
  "parser_version": "0.1.0",
  "parser_config_hash": "sha256...",
  "elements": [
    {
      "element_id": "el_001",
      "element_type": "heading",
      "text": "第2章 性能测试",
      "normalized_text": "第2章 性能测试",
      "level": 1,
      "page": 8,
      "bbox": null,
      "section_path": ["第2章 性能测试"],
      "order": 1,
      "metadata": {}
    },
    {
      "element_id": "el_002",
      "element_type": "paragraph",
      "text": "P99 延迟在 5000 QPS 后明显上升。",
      "normalized_text": "P99 延迟在 5000 QPS 后明显上升。",
      "page": 9,
      "bbox": [100, 120, 500, 180],
      "section_path": ["第2章 性能测试", "2.3 压测结果"],
      "order": 2,
      "metadata": {}
    }
  ],
  "document_metadata": {
    "source_path": "report.pdf",
    "file_ext": ".pdf",
    "checksum": "sha256...",
    "last_modified_datetime": "2026-04-27T10:00:00+08:00"
  },
  "parser_raw_ref": "artifact://parser_raw/parsed_doc_001.json"
}
```

`element_type` 第一阶段建议支持：

```text
heading
paragraph
table
list
code
figure
formula
page_header
page_footer
footnote
unknown
```

为了兼容 AutoRAG 这类轻量流程，还可以从上述结构派生一个简单文本视图：

```text
texts
path
page
last_modified_datetime
```

但这个简单视图只作为兼容层，不作为 SmartRAG 的唯一内部表示。

#### 5.7.2 策略 + 适配器模式

每个解析工具实现一个唯一的 parser strategy。

最小接口：

```python
class ParserStrategy:
    name: str
    description: str
    supported_file_exts: list[str]

    def config_schema(self) -> dict:
        ...

    def default_config(self) -> dict:
        ...

    def parse(self, file: MaterialFile, config: dict, context: ParseContext) -> ParserRawResult:
        ...

    def normalize(self, raw_result: ParserRawResult, context: ParseContext) -> NormalizedParsedDocument:
        ...
```

也可以拆成两层：

```text
ParserStrategy.parse()
  -> 调用具体工具，得到工具原始输出

ParserAdapter.normalize()
  -> 把工具原始输出转成 SmartRAG ParsedDocument
```

这样做的意义：

- 接入新解析工具时，只新增 strategy/adapter，不改主流程。
- 第三方工具输出格式变化时，只改 adapter。
- chunker 永远只面向统一的 `NormalizedParsedDocument`。
- UI 可以自动读取 strategy 的 `name` 和 `description`。
- Agent 可以根据 description 和历史效果推荐 parser。

#### 5.7.3 解析工具唯一名称与描述

每个解析工具必须声明唯一 `name`。

示例：

```json
{
  "name": "llama_parse",
  "display_name": "LlamaParse",
  "description": "适合 PDF、表格和复杂版面文档解析，可输出 text、markdown 或 json，支持多模态解析。",
  "supported_file_exts": [".pdf", ".docx", ".pptx"],
  "capabilities": ["layout", "table", "ocr", "markdown"],
  "config_schema_ref": "parser_configs/llama_parse.schema.json"
}
```

约束：

- `name` 全局唯一，作为系统内部引用。
- `display_name` 用于 UI 展示。
- `description` 必填，用于用户选择和 Agent 决策。
- `supported_file_exts` 必填，用于默认规则匹配。
- `capabilities` 用于筛选工具，例如 `ocr`、`table`、`layout`、`fast`、`cheap`。

#### 5.7.4 自动扫描与注册

系统启动时自动扫描解析工具，不应要求开发者手动维护 UI 下拉配置。

扫描来源：

```text
built_in_parsers/
custom_parsers/
python entrypoints
enabled plugins
```

扫描流程：

```text
scan parser modules
-> validate ParserStrategy interface
-> validate unique name
-> load description and config_schema
-> register to ParserRegistry
-> expose to API/UI/MCP
```

UI 获取解析工具列表时只调用：

```text
GET /api/parser-strategies
```

返回：

```json
[
  {
    "name": "pymupdf",
    "display_name": "PyMuPDF",
    "description": "速度快，适合文本型 PDF，能保留页码和部分 block 信息。",
    "supported_file_exts": [".pdf"],
    "capabilities": ["pdf", "fast", "page"]
  },
  {
    "name": "llama_parse",
    "display_name": "LlamaParse",
    "description": "适合复杂 PDF、表格和版面解析，成本较高。",
    "supported_file_exts": [".pdf", ".docx", ".pptx"],
    "capabilities": ["layout", "table", "ocr", "markdown"]
  }
]
```

#### 5.7.5 YAML 配置

对于需要额外配置的解析工具，配置写在 YAML 中，并由 parser strategy 提供 schema 校验。

示例：

```yaml
parser:
  name: llama_parse
  config:
    result_type: markdown
    language: zh
    use_vendor_multimodal_model: true
    vendor_multimodal_model_name: openai-gpt-4o-mini
```

另一个示例：

```yaml
parser:
  name: table_hybrid
  config:
    table_detection:
      method: pdfplumber
    text_parser:
      name: pymupdf
      config: {}
    table_parser:
      name: llama_parse
      config:
        result_type: markdown
```

配置要求：

- YAML 中只保存工具参数，不保存密钥明文。
- 密钥通过 `model_id`、`secret_ref` 或环境变量引用。
- 每次真实执行都保存 `parser_config_hash`。
- UI 编辑 YAML 时必须根据 `config_schema` 做校验。

#### 5.7.6 与默认处理规则的关系

后缀默认处理规则不应该手写 parser 下拉选项，而应该引用 ParserRegistry。

例如 `.pdf` 默认规则：

```json
{
  "file_ext": ".pdf",
  "parser_name": "pymupdf",
  "parser_config": {
    "extract_images": false
  },
  "chunker_plugin_id": "chunker.section_aware"
}
```

当新增一个解析工具时：

```text
新增 ParserStrategy 文件
-> 系统自动扫描
-> UI 自动出现该工具
-> 用户可以把它配置为某后缀默认 parser
```

不需要开发者再去额外修改 UI 配置或数据库枚举。

#### 5.7.7 解析工具质量报告

由于不同 parser 的效果差异会影响后续 RAG，解析阶段需要输出质量报告。

建议记录：

- 是否成功。
- 解析耗时。
- 输出 element 数量。
- 空文本比例。
- 页码覆盖率。
- 表格数量。
- heading 数量。
- OCR 使用情况。
- 错误和 warning。
- parser 原始输出 artifact。

这些信息会进入 Agent observation，用于后续推荐更合适的 parser。

### 5.8 设置页面：原始材料默认处理策略

系统设置页面需要提供“原始材料管理”配置区，允许用户按文件后缀设置默认处理策略。

配置维度：

| 字段 | 示例 |
|---|---|
| 文件后缀 | `.pdf`、`.docx`、`.xlsx`、`.md`、`.log` |
| 默认解析处理器 | `pymupdf`、`unstructured`、`docx_parser` |
| 默认 OCR 策略 | `none`、`auto`、`force` |
| 默认表格策略 | `extract_table`、`table_as_markdown` |
| 默认 chunk 策略 | `section_aware`、`recursive`、`row_based` |
| 默认 metadata 策略 | `basic`、`section_path`、`date_service` |
| 是否拼接 metadata 到 embedding_text | true / false |
| 默认 embedding_text 模板 | `title + section_path + content` |

配置示例：

```json
{
  ".pdf": {
    "parser": "pymupdf",
    "ocr": "auto",
    "chunker": "section_aware",
    "metadata_strategy": "section_path",
    "embedding_text_template": "title_section_content"
  },
  ".xlsx": {
    "parser": "excel_structured",
    "chunker": "sheet_table_row_group",
    "metadata_strategy": "sheet_header_row",
    "embedding_text_template": "sheet_header_content"
  },
  ".log": {
    "parser": "log_parser",
    "chunker": "time_window",
    "metadata_strategy": "date_service_level",
    "embedding_text_template": "date_service_message"
  }
}
```

### 5.9 默认配置与实际处理的关系

默认配置只作为初始建议，不应该锁死真实处理。

真实处理时：

1. 系统根据文件后缀加载默认 parser/chunker/metadata 策略。
2. UI 展示即将使用的默认配置。
3. 用户可以在批次级别或文件级别覆盖配置。
4. 实际执行的配置生成 config hash。
5. 后续 parse、chunk、embedding 都绑定实际 config hash。

配置优先级：

```text
file override
  > batch override
  > project default by extension
  > system default
```

### 5.10 UI 页面设计

材料批次列表页：

- 批次名称。
- `batch_id`。
- 当前版本。
- 文件数。
- 最近更新时间。
- 最近解析状态。
- 最近 corpus 版本。
- 最近质量报告。

批次详情页：

- 文件列表。
- 文件状态：active / removed。
- 文件 checksum。
- 文件大小。
- 文件类型。
- 上传时间。
- 当前默认 parser/chunker。
- 单文件新增。
- 单文件逻辑删除。
- 创建新版本记录。

批次版本页：

- 版本号。
- 变更说明。
- 新增文件。
- 删除文件。
- active 文件快照。
- 关联 parse run。
- 关联 corpus version。
- 关联 eval dataset。
- 关联质量报告。

设置页原始材料管理区：

- 按后缀配置默认解析处理器。
- 按后缀配置默认 chunk 策略。
- 按后缀配置 metadata 策略。
- 配置 embedding_text 模板。
- 测试某个文件会命中哪条默认规则。
- 解析处理器列表从 ParserRegistry 自动读取，展示唯一名称、描述、支持后缀和能力标签。
- 对需要额外配置的解析器，提供 YAML 编辑器和 schema 校验。

### 5.11 MCP 与 Agent 工具预留

原始材料管理需要暴露 MCP tools：

```text
list_material_batches
get_material_batch
list_batch_versions
list_batch_files
get_batch_manifest
inspect_file_metadata
get_default_processing_rules
propose_processing_rule_update
list_parser_strategies
get_parser_strategy
validate_parser_config
```

高风险写操作建议走 proposal：

```text
propose_batch_file_deletion
propose_processing_rule_update
```

Agent 可读取：

- 批次文件类型分布。
- 批次版本变化。
- 默认处理规则。
- 可用解析工具名称、描述和能力。
- 文件解析失败统计。
- 文件级质量报告。

Agent 可建议：

- 某类文件更换 parser。
- 某个批次使用特定 chunk 策略。
- 某类后缀新增 metadata 策略。

### 5.12 数据表初稿

核心表：

```text
material_batches
material_batch_versions
material_files
material_file_events
material_batch_manifests
processing_default_rules
file_processing_overrides
batch_processing_overrides
parser_strategies
parser_strategy_versions
parse_runs
parsed_documents
```

`material_batches`：

```text
batch_id
project_id
batch_name
description
current_version_id
created_by
created_at
updated_at
```

`material_files`：

```text
file_id
batch_id
original_filename
file_ext
mime_type
size_bytes
checksum
storage_uri
status
created_at
removed_at
```

`material_batch_versions`：

```text
batch_version_id
batch_id
version_number
parent_version_id
change_type
active_file_ids_snapshot
manifest_uri
created_by
created_at
```

`processing_default_rules`：

```text
rule_id
project_id
file_ext
parser_name
parser_config_yaml
chunker_plugin_id
metadata_strategy_id
embedding_text_template_id
priority
enabled
created_at
updated_at
```

`parser_strategies`：

```text
parser_name
display_name
description
supported_file_exts
capabilities
config_schema
source
enabled
loaded_at
```

`parse_runs`：

```text
parse_run_id
batch_id
batch_version_id
parser_name
parser_config_hash
status
started_at
ended_at
quality_report_uri
```

`parsed_documents`：

```text
parsed_document_id
parse_run_id
file_id
parser_name
parser_config_hash
normalized_output_uri
parser_raw_ref
content_hash
created_at
```

### 5.13 第一阶段范围

MVP 必须支持：

- 新建材料批次。
- 批量上传文件。
- 批次内新增文件。
- 批次内逻辑删除文件。
- 批次版本记录。
- 文件 checksum。
- 文件后缀默认处理规则。
- 自动扫描内置 parser strategy。
- UI 自动展示解析工具唯一名称、描述、支持后缀和能力标签。
- 解析工具 YAML 配置和 schema 校验。
- 解析输出归一化为 `NormalizedParsedDocument`。
- 真实处理前展示默认 parser/chunker/metadata 策略。
- 批次级覆盖默认配置。
- 批次版本绑定后续 parse/corpus/eval dataset。

MVP 可暂缓：

- URL/Confluence/Jira 接入。
- Git-like 内容寻址。
- 复杂权限。
- 跨批次文件去重。
- 文件夹双向同步。
- Agent 自动更新默认处理规则。

## 6. 解析与信息提取

解析层负责把不同格式的原始材料转成可处理的结构化中间表示。

在 SmartRAG 中，解析不是一个固定预处理步骤，而是第一个可实验、可比较、可观测的策略节点。不同 parser 会显著影响后续 chunk、metadata、检索命中和引用溯源，因此解析策略需要进入实验空间，并能在 UI 中被清晰配置和对比。

解析目标：

- 文本抽取。
- 标题层级识别。
- 段落和阅读顺序恢复。
- 表格抽取。
- 图片、图表、公式、caption 定位。
- OCR。
- metadata 提取，例如作者、日期、页码、章节、文件路径。

不同文档类型的策略：

| 类型 | 解析重点 |
|---|---|
| PDF | OCR、版面分析、章节层级、表格、页码 |
| Word | 标题样式、段落、表格、批注 |
| Excel | sheet、表头、行列、公式、备注列、图表数据源 |
| Markdown/HTML | 标题树、链接、代码块、表格 |
| 运维日志 | 时间、服务名、级别、trace_id、事件窗口 |
| 聊天记录 | 发送人、时间、会话、回复关系、消息类型 |

首批建议集成的解析模块：

| 模块类型 | 候选实现 | 适用场景 |
|---|---|---|
| text parser | markdown、txt、html parser | 结构清晰的文本材料 |
| PDF parser | PyMuPDF、pdfplumber、unstructured、LlamaParse adapter | 普通 PDF、报告、论文 |
| OCR parser | PaddleOCR、Tesseract、云 OCR adapter | 扫描件、图片型 PDF |
| office parser | python-docx、openpyxl、unstructured | Word、Excel、PPT |
| table parser | camelot、tabula、table-transformer adapter | 表格密集型材料 |
| custom parser | Python class、HTTP service、MCP tool | 企业内部格式或垂直场景 |

解析节点需要暴露的核心配置：

- parser 类型和版本。
- 是否启用 OCR。
- OCR 语言、dpi、页面范围。
- 是否抽取表格、图片、公式、caption。
- 是否保留版面坐标和页码。
- 标题层级识别策略。
- metadata 抽取策略。
- 失败页处理策略。

解析质量需要被量化展示：

- 成功解析文件数、失败文件数、失败原因。
- 文本覆盖率、OCR 页数、空文本页数。
- 标题层级数量、表格数量、图片数量。
- 每个文档的解析耗时和成本。
- 抽样预览：原始页面、解析文本、结构树、metadata 对照。

输出示例：

```json
{
  "doc_id": "doc_001",
  "elements": [
    {
      "type": "heading",
      "text": "第2章 性能测试",
      "level": 1,
      "page": 8
    },
    {
      "type": "paragraph",
      "text": "P99 延迟在 5000 QPS 后明显上升。",
      "section_path": ["第2章 性能测试", "2.3 压测结果"],
      "page": 9
    }
  ],
  "metadata": {
    "title": "系统稳定性评估报告",
    "author": "运维组",
    "last_modified_datetime": "2026-04-26T10:00:00+08:00"
  }
}
```

## 7. Corpus 与 Chunk 构建

Corpus Builder 负责从 ParsedDocument 生成可检索的 chunk 集合。

Chunk 构建是 SmartRAG 的核心实验节点之一。它不只决定文本切分长度，还决定语义边界、metadata 是否参与向量化、上下文扩展方式、引用粒度和评测 ground truth 映射方式。系统应支持同一批解析产物生成多个 corpus version，并在后续实验中复用。

每个 chunk 建议保存三类内容：

```json
{
  "chunk_id": "chunk_001",
  "doc_id": "doc_001",
  "content": "P99 延迟在 5000 QPS 后明显上升。",
  "embedding_text": "文档：系统稳定性评估报告\n章节：第2章 性能测试 > 2.3 压测结果\n正文：P99 延迟在 5000 QPS 后明显上升。",
  "metadata": {
    "source_path": "report.pdf",
    "page_start": 9,
    "page_end": 9,
    "section_path": ["第2章 性能测试", "2.3 压测结果"],
    "section_number": "2.3",
    "author": "运维组",
    "last_modified_datetime": "2026-04-26T10:00:00+08:00",
    "prev_chunk_id": "chunk_000",
    "next_chunk_id": "chunk_002"
  }
}
```

需要支持的候选策略：

- 固定长度 chunk。
- 递归文本分块。
- 标题/章节感知分块。
- 表格行/表格块分块。
- 聊天记录按时间窗口或话题窗口分块。
- 运维日志按时间窗口、事件窗口、服务维度分块。
- metadata 是否拼入 `embedding_text`。
- metadata 拼接模板对比。
- overlap 大小对比。
- parent-child chunk。
- small-to-big chunk。
- semantic chunk。
- late chunking。
- 按章节、页码、标题、时间窗口、会话窗口、表格块等结构切分。
- chunk 后自动生成 section summary 或 parent summary。

Chunk 节点需要暴露的配置面：

```yaml
chunker:
  module_type: section_aware
  chunk_size: [512, 1024, 1536]
  chunk_overlap: [64, 128]
  split_by_heading: true
  preserve_table: true
  embedding_text_template:
    - "{title}\n{section_path}\n{content}"
    - "{content}"
  metadata_fields:
    - source_path
    - page
    - section_path
    - last_modified_datetime
```

每个 corpus version 需要记录：

- 使用的 parsed artifact。
- chunker 模块和参数。
- chunk 数量、平均长度、P50/P90/P99 长度。
- metadata 完整度。
- embedding_text 模板。
- 是否包含 prev/next、parent/child、section summary。
- 后续索引构建状态。

重要原则：

- `content` 用于展示和最终上下文。
- `embedding_text` 用于向量化，可以包含部分语义 metadata。
- `metadata` 用于过滤、排序、溯源、权限和上下文扩展。

## 8. 测评集构建

测评集来源分三类：

1. 自动合成测评集。
2. 用户上传标注数据。
3. 真实查询日志加人工或 LLM 辅助标注。

内部统一格式：

```json
{
  "qid": "q001",
  "query": "4月26日 Redis 出过什么问题？",
  "reference_answer": "Redis 连接数达到阈值，扩容后恢复。",
  "reference_context_ids": ["chunk_001"],
  "reference_contexts": ["2026-04-26 10:10 Redis 连接数达到阈值。"],
  "metadata": {
    "query_type": "time_filter",
    "doc_type": "ops_log"
  }
}
```

自动合成流程参考 AutoRAG，但做成可扩展：

```text
sample evidence chunks
-> generate query
-> generate reference answer
-> filter bad QA
-> optional query evolve
```

后续可接入：

- AutoRAG-style retrieval_gt 构建。
- RAGAS testset generation。
- 自定义业务问答生成 prompt。
- 真实用户 query 导入。

测评集构建需要支持“生成、清洗、审核、版本化”四个阶段。系统不能把合成 QA 直接视为可信评测集，必须保留样本来源、证据 chunk、生成模型、prompt 版本、过滤规则和人工审核状态。

测评集样本应覆盖不同问题类型：

- 单事实查询。
- 多跳查询。
- 时间范围查询。
- metadata filter 查询。
- 对比类查询。
- 汇总类查询。
- 表格/数字查询。
- 无答案或应回答不知道的问题。

评测集 UI 需要支持：

- 从 corpus 中抽样生成 QA。
- 导入 CSV/JSON/Parquet 标注数据。
- 对 query、reference answer、reference context 进行人工审核。
- 标记低质量样本、重复样本、证据不完整样本。
- 按 query type、doc type、难度、语言筛选样本。
- 将 eval dataset 固定版本绑定到实验，保证结果可复现。

## 9. 检索前处理与 Query Expansion

Query Processor 负责把用户原始问题转换成更适合检索的请求。

Query Processor 是连接用户问题和检索系统的前置策略节点。它可以是简单的 raw query，也可以包含 query rewrite、multi-query、decomposition、HyDE 和 metadata extraction。每个策略都应被视为可插拔模块，并可在后续 retrieval 节点中被单独评测。

候选策略：

- Raw query：原始问题直接检索。
- Query rewrite：改写成长短适中、语义明确的问题。
- Query condensation：结合多轮对话历史改写问题。
- Multi-query：生成多个同义问题并行检索。
- Query decomposition：复杂问题拆成多个子问题。
- HyDE：生成假想答案或假想文档后检索。
- Metadata extraction：抽取时间、作者、章节、服务名、错误码等过滤条件。

需要支持的配置：

- 是否启用多轮上下文 condensation。
- rewrite prompt 和模型。
- multi-query 数量。
- decomposition 最大子问题数。
- HyDE 生成文档数量和长度。
- metadata schema 与字段抽取规则。
- query expansion 结果是否去重。
- 不同 query 之间的检索权重。

输出示例：

```json
{
  "semantic_queries": [
    "2026-04-26 Redis 连接数上涨原因",
    "2026-04-26 Redis 故障恢复措施"
  ],
  "metadata_filter": {
    "date": "2026-04-26",
    "service": "redis"
  },
  "strategy": "decomposition + metadata_filter"
}
```

## 10. 检索策略

Retrieval Engine 支持多种检索通道。

检索节点应同时支持“单通道检索”和“多通道检索融合”。用户在 UI 中需要能选择检索模块、索引版本、top_k、过滤条件和融合权重，并把这些参数声明为固定值或搜索空间。

基础检索器：

- Dense vector retrieval。
- BM25 sparse retrieval。
- Hybrid retrieval。
- Metadata filter + retrieval。
- ColBERT / late interaction，作为高级候选。
- Graph retrieval，作为后续高级候选。
- SQL / structured retrieval，作为结构化数据候选。

融合策略：

- 单路检索。
- 多 query 并行检索。
- BM25 + dense RRF 融合。
- BM25 + dense + HyDE 融合。
- Weighted score fusion。
- Union candidates + reranker。
- Router based retrieval。

混合检索需要重点支持自定义权重：

```yaml
retriever:
  module_type: hybrid_rrf
  channels:
    - name: bm25
      weight: [0.3, 0.5, 0.7]
    - name: dense
      weight: [0.3, 0.5, 0.7]
  top_k: [5, 10, 20]
  rrf_k: [20, 60]
```

检索结果必须保存完整候选列表，而不只保存最终 top_k：

- 每路 retriever 的原始分数。
- metadata filter 命中情况。
- fusion 前后的 rank。
- 被过滤或截断的候选。
- 与 retrieval_gt 的命中关系。
- 每个 query expansion 分支的贡献。

推荐初版策略空间：

```yaml
retrieval_channels:
  - dense
  - bm25
  - dense_bm25_rrf
  - dense_bm25_hyde_rrf

top_k:
  - 5
  - 10
  - 20
```

## 11. 检索后处理

Post-Retrieval Processor 负责对初召回结果进行加工。

检索后处理用于把“候选文档列表”变成“适合 LLM 使用的上下文”。这一层需要拆成多个可选节点，而不是混在 retriever 或 generator 内部。

候选模块：

- Reranker：cross-encoder、BGE、Cohere、Jina、ColBERT。
- Passage filter：过滤低相关结果。
- Passage augmenter：补充前后 chunk、父 chunk、章节摘要。
- Passage compressor：压缩长上下文。
- Dedup：去重。
- Context packing：决定最终放进 LLM 的上下文顺序和长度。
- Citation builder：构造可溯源引用。
- Safety / permission filter：根据权限或敏感信息规则过滤上下文。

需要支持的实验变量：

- 是否启用 reranker。
- reranker 类型。
- 初召回 top_k 和 rerank 后 top_k。
- 是否补充 prev/next chunk。
- 是否加入 section summary。
- 最终上下文 token budget。
- context packing 顺序，例如按相关性、原文顺序、章节顺序、时间顺序。
- 是否保留被丢弃上下文以供失败分析。

后处理节点需要输出两类内容：

- `candidate_contexts`：包含分数、rank、来源和处理历史的候选上下文。
- `final_contexts`：实际进入 prompt 的上下文片段及顺序。

## 12. 生成层

Generator 负责根据 query 和上下文生成答案。

生成层既是最终用户可见结果的产生节点，也是生成类评测指标的输入节点。系统需要支持多个 prompt template、多个 LLM、多个输出约束同时进入实验空间。

候选变量：

- LLM 模型。
- prompt template。
- system prompt。
- 是否要求引用来源。
- 是否允许回答不知道。
- temperature。
- context ordering。
- answer style。
- max_tokens。
- 是否结构化输出。
- 是否启用 function calling / tool calling。
- 是否强制基于引用回答。
- 不足以回答时的拒答策略。

输出应包含：

```json
{
  "answer": "4月26日 Redis 连接数达到阈值，扩容后恢复。",
  "citations": [
    {
      "chunk_id": "chunk_001",
      "source_path": "ops.log",
      "date": "2026-04-26"
    }
  ]
}
```

生成层 trace 需要保存：

- system prompt、user prompt、context 拼装结果。
- 使用的模型、temperature、max_tokens。
- token usage、latency、cost。
- 原始模型输出和结构化解析结果。
- 引用与实际使用 chunk 的映射。

## 13. 评测系统

评测层要做成可插拔 adapter。

评测系统是 SmartRAG 的决策核心。所有优化器、leaderboard、最佳策略导出都只能基于统一后的评测结果，而不能直接依赖某一个评测框架的私有输出格式。

第一版内置：

- IR 指标：Recall@k、Precision@k、MRR、NDCG。
- 生成指标：answer correctness、answer relevancy、faithfulness。
- RAGAS adapter。
- DeepEval adapter。
- 自定义 Python metric。
- 成本和延迟指标。
- 人工评审入口。

统一结果格式：

```json
{
  "run_id": "run_001",
  "config_id": "cfg_001",
  "scores": {
    "recall_at_5": 0.82,
    "mrr": 0.71,
    "faithfulness": 0.88,
    "answer_correctness": 0.84,
    "latency_ms": 1200,
    "cost": 0.02
  },
  "per_sample": []
}
```

未来可接入：

- RAGAS。
- DeepEval。
- TruLens。
- ARES。
- OpenAI Evals。
- LangSmith evaluators。
- Human review。

评测需要分为三个层级：

| 层级 | 评测对象 | 典型指标 |
|---|---|---|
| Retrieval evaluation | query -> retrieved chunks | Recall@k、Precision@k、MRR、NDCG、Hit Rate |
| Context evaluation | query + final contexts | context precision、context recall、context relevancy、冗余率 |
| Generation evaluation | query + contexts -> answer | correctness、faithfulness、answer relevancy、citation accuracy |

多目标排序需要支持权重和约束：

```yaml
selection:
  score:
    answer_correctness: 0.35
    faithfulness: 0.25
    recall_at_5: 0.25
    citation_accuracy: 0.10
    cost: -0.05
  constraints:
    max_latency_ms: 3000
    max_cost_per_100_queries: 2.0
```

Leaderboard 不只展示总分，还需要能展开到节点级和样本级，回答以下问题：

- 哪个 parser/chunker 组合让 retrieval recall 更高。
- 哪个 query expansion 策略带来了更多命中。
- 哪个 reranker 提升了最终正确率但增加了多少延迟。
- 哪些样本所有策略都失败，可能是测评集或材料本身有问题。

## 14. 优化器与 Agent

优化器负责从候选策略空间中找最佳配置。

SmartRAG 的调优体验应当像搭积木：用户先定义可用模块和参数空间，系统负责枚举、剪枝、执行、评测和排序。Agent 不是第一阶段的必需执行者，但架构上要允许 Agent 后续读取观测数据、提出策略修改建议，并通过 MCP 工具发起受控实验。

建议采用混合模式：

```text
LLM Agent 负责理解文档、分析失败样本、提出策略空间调整。
Bayesian Optimization / Bandit / Grid Search 负责稳定执行搜索。
Evaluator 负责打分。
```

第一阶段建议优先实现三类搜索方式：

- Grid Search：适合小规模、可解释的参数组合。
- Preset Search：内置常见 RAG 策略模板，例如 naive、dense、bm25、hybrid、hybrid+rerank。
- Successive Narrowing：先用小测试集粗筛，再用完整测试集评测候选 top N。

后续可扩展：

- Bayesian Optimization。
- Bandit。
- Evolutionary Search。
- Agent-guided Search Space Refinement。
- 基于历史项目的 warm start。

优化目标支持多目标：

```yaml
objective:
  maximize:
    answer_correctness: 0.4
    faithfulness: 0.3
    recall_at_5: 0.2
  minimize:
    latency_ms: 0.1
```

Agent 可执行任务：

- 判断文档类型。
- 设计 metadata schema。
- 推荐 parser/chunker/search space。
- 分析失败样本。
- 提出下一轮实验组合。
- 解释为什么某个策略胜出。

Agentic 调优需要遵循“建议优先、执行受控”的原则：

- Agent 可以生成 strategy proposal，但不能直接覆盖最佳策略。
- Agent 可以请求发起实验，但需要通过权限和预算检查。
- Agent 可以扩展搜索空间，但必须展示新增模块、参数范围和预计成本。
- Agent 可以分析失败样本，但需要引用 trace、artifact 和评测结果。
- Agent 的每次建议、执行和结果都要作为事件记录，便于审计和回放。

策略提案格式示例：

```json
{
  "proposal_id": "proposal_001",
  "reason": "time_filter 类型问题 retrieval recall 较低，疑似 metadata extraction 未启用。",
  "changes": [
    {
      "node": "query_processor",
      "add_module": "metadata_extractor",
      "config": {
        "fields": ["date", "service"]
      }
    },
    {
      "node": "retriever",
      "update_search_space": {
        "top_k": [10, 20, 40]
      }
    }
  ],
  "estimated_cost": 1.2,
  "requires_approval": true
}
```

## 15. Web UI

Web UI 是 SmartRAG 区别于底层 RAG 框架的核心能力。UI 不应该只是展示结果的 dashboard，而应该是一个完整的 RAG 实验工作台，覆盖项目初始化、材料处理、流程编排、参数搜索空间配置、实验执行、评测分析和最佳策略导出。

UI 设计目标：

- 让用户以“流程节点 + 模块卡片 + 参数面板”的方式搭建 RAG pipeline。
- 复杂配置可视化，但所有配置都能导出为 YAML/JSON。
- 每个模块的配置项由 schema 驱动生成，减少前端硬编码。
- 实验运行过程可追踪，失败可定位，结果可比较。
- 既支持新手使用预设模板，也支持高级用户细调参数空间。

Web UI 分为几个页面：

1. **项目首页**
   - 项目列表。
   - 数据源数量。
   - 最近实验状态。
   - 当前最佳策略。

2. **材料管理**
   - 上传文件。
   - 查看解析结果。
   - 查看文档结构树。
   - 查看 metadata。

3. **Corpus 版本**
   - 查看不同 chunk 策略生成的 corpus。
   - 对比 chunk 数量、平均长度、metadata 完整度。
   - 预览 chunk 和原文溯源。

4. **测评集**
   - 自动生成 QA。
   - 导入人工 QA。
   - 查看 query、reference answer、reference context。
   - 标记坏样本。

5. **实验配置**
   - 选择候选 parser、chunker、query processor、retriever、fusion、reranker、post processor、generator、evaluator。
   - 使用流程画布或分步骤向导连接完整 pipeline。
   - 配置每个模块的固定参数和搜索空间。
   - 使用预设策略模板快速生成候选组合。
   - 配置优化目标。
   - 预估组合数量、运行成本和耗时。
   - 启动实验。

6. **实验看板**
   - leaderboard。
   - 每个 config 的指标。
   - 成本、延迟、token。
   - Pareto frontier。
   - 节点级 best result。
   - trial summary。
   - run trace。

7. **失败样本分析**
   - 检索失败。
   - 生成失败。
   - 幻觉。
   - metadata filter 失败。
   - Agent 建议下一轮实验。
   - 对比不同策略在同一样本上的 retrieved contexts 和 final answer。
   - 标记测评样本问题。

8. **最佳策略导出**
   - 导出 YAML/JSON。
   - 导出可运行 pipeline。
   - 查看部署说明。

关键 UI 组件：

| 组件 | 作用 |
|---|---|
| Pipeline Canvas | 展示全流程节点和连接关系 |
| Module Picker | 按节点类型选择内置或自定义模块 |
| Config Panel | 根据 schema 配置模块参数 |
| Search Space Editor | 将参数设置为固定值、枚举值或范围 |
| Cost Estimator | 根据组合数、样本数、模型价格估算成本 |
| Run Monitor | 展示运行进度、队列、失败节点、重试状态 |
| Leaderboard | 展示总分、分项指标、成本、延迟 |
| Trace Viewer | 展示单样本从 query 到 answer 的完整链路 |
| Failure Analyzer | 聚合失败类型和代表样本 |
| Export Center | 导出配置、报告、pipeline bundle |

UI 中的“搭积木”体验建议支持两种模式：

- **向导模式**：适合新用户，按材料、corpus、测评集、策略、运行、结果逐步配置。
- **画布模式**：适合高级用户，以节点图方式配置流程和分支。

### 15.1 国际化与多语言

Web UI 需要从第一版开始支持多语言，MVP 至少支持中文和英文切换，后续可以扩展更多语言。

基本要求：

- UI 文案不能硬编码在组件中。
- 所有菜单、按钮、表单标签、提示、错误信息、空状态、确认弹窗都必须走 i18n key。
- 默认支持 `zh-CN` 和 `en-US`。
- 用户可以在 UI 中切换语言。
- 系统保存用户语言偏好。
- 未登录状态可以使用浏览器语言或系统默认语言。
- 新增语言时只需要新增语言包，不应修改业务代码。

语言包示例：

```text
locales/
  zh-CN/
    common.json
    material.json
    experiment.json
    evaluation.json
    model.json
  en-US/
    common.json
    material.json
    experiment.json
    evaluation.json
    model.json
```

i18n key 示例：

```json
{
  "material.batch.create": "新建材料批次",
  "material.batch.uploadFiles": "上传文件",
  "model.connection.available": "连接成功",
  "model.connection.failed": "连接失败",
  "experiment.run.start": "启动实验"
}
```

后端也需要配合：

- API 错误返回稳定 `error_code`，前端按语言包展示。
- 后端日志仍使用稳定英文 code，避免多语言影响排障。
- Agent prompt 默认语言可以跟随用户语言，但实验配置需要记录 prompt 版本和语言。
- 质量报告和 Agent 分析报告应支持按用户语言生成。

语言偏好优先级：

```text
user preference
  > project preference
  > browser language
  > system default zh-CN
```

后续扩展语言时需要考虑：

- 日期、数字、货币、token/cost 格式本地化。
- 中英文文本长度差异导致的 UI 布局适配。
- Prompt 模板语言是否与 UI 语言独立配置。
- 测评集生成语言和 UI 语言应该分开管理。

## 16. 存储设计初稿

建议先使用：

- PostgreSQL：项目、数据源、实验、评测结果、metadata。
- 对象存储或本地文件：原始文件、解析产物、parquet。
- 向量库：Qdrant / Chroma / Milvus，初期可用 Qdrant 或 Chroma。
- SQLite：可用于本地 demo 模式。

核心表：

```text
projects
data_sources
parsed_documents
corpus_versions
chunks
eval_datasets
eval_samples
rag_configs
rag_runs
evaluation_results
best_strategies
```

为了支撑可复现实验和 Agentic 调优，还需要补充 artifact 与 trace 相关表：

```text
material_batches
artifacts
artifact_links
experiment_graphs
experiment_nodes
experiment_node_runs
trace_events
module_registry
module_versions
strategy_proposals
mcp_audit_logs
```

关键存储原则：

- 原始材料不可被实验过程覆盖，只能产生新版本或新 artifact。
- 每个 artifact 必须记录来源、生成模块、配置 hash、输入 artifact ids。
- 每次 run 必须绑定 eval dataset version，避免不同评测集结果混比。
- 最佳策略只保存引用和配置，不复制大体积产物。
- trace 和 per-sample result 要能按 run、config、qid、node 查询。
- 导出的 pipeline bundle 必须包含配置、模块版本、模型引用和必要的资源清单。

## 17. 第一阶段 MVP

MVP 目标：能跑通一个端到端、UI 可操作、结果可解释的 RAG 策略优化闭环。

MVP 不追求一次覆盖所有高级模块，而是要证明以下核心假设：

- 用户可以从 UI 导入材料并生成可复用 corpus。
- 用户可以在 UI 中选择模块和参数搜索空间。
- 系统可以自动运行多组 RAG 配置并评测。
- 用户可以看懂为什么某个配置更好。
- 最佳配置可以导出并复现。

范围：

- 支持 PDF、Markdown、TXT。
- 支持基础 parse。
- 支持三种 chunk 策略。
- 支持 metadata 拼接策略。
- 支持 raw query、multi-query、HyDE 至少两种 query processor。
- 支持 dense、BM25、hybrid 检索。
- 支持 hybrid 权重配置。
- 支持 reranker 开关。
- 支持基础 post processor，例如 prev/next augmenter、dedup、context packing。
- 支持 AutoRAG-style synthetic QA。
- 支持 IR 指标和 RAGAS adapter。
- 支持 leaderboard。
- 支持单样本 trace 查看。
- 支持失败样本列表。
- 支持导出最佳策略。

MVP 流程：

```text
上传文档
-> 解析
-> 生成多个 corpus version
-> 自动生成 QA 测评集
-> 在 UI 中选择流程模块和参数搜索空间
-> 跑多组 RAG 配置
-> 评分并生成 leaderboard
-> 展示最佳策略、trace 和失败样本
-> 导出 YAML/JSON pipeline
```

MVP 推荐内置策略模板：

| 模板 | 流程 |
|---|---|
| naive_rag | parse -> fixed chunk -> dense retrieval -> prompt -> generator |
| bm25_rag | parse -> recursive chunk -> BM25 -> prompt -> generator |
| hybrid_rag | parse -> section chunk -> dense + BM25 RRF -> prompt -> generator |
| hybrid_rerank_rag | parse -> section chunk -> dense + BM25 RRF -> reranker -> context packing -> generator |
| query_expansion_rag | parse -> chunk -> multi-query/HyDE -> hybrid retrieval -> reranker -> generator |

MVP 暂缓：

- Agent 自动生成插件。
- 复杂 DAG 分支、循环和跨节点条件执行。
- 多租户权限和企业级审计。
- 分布式任务执行。
- 完整插件市场。
- 多模态检索和图检索。
- 生产级在线服务编排。

## 18. 后续讨论问题

需要继续明确的问题：

- 第一批文档类型优先支持哪些。
- 是否先做本地单机版，还是直接做 Web 服务。
- 是否需要多用户和权限。
- 是否默认接入 OpenAI、Ollama、还是企业内部模型。
- 测评集生成是否优先 AutoRAG-style，还是同时接 RAGAS。
- metadata schema 是否由 Agent 自动推荐，还是先用规则模板。
- 评测目标默认权重如何设置。
- 最佳策略导出成 LangChain、LlamaIndex，还是自研 pipeline。
- 第一版 UI 优先做向导模式，还是直接做流程画布。
- 内置模块优先全面覆盖 AutoRAG，还是先实现最常用模块并预留 adapter。
- 实验执行是先用本地同步/后台任务，还是第一版就接队列。
- 是否需要兼容 AutoRAG 的 qa/corpus parquet 格式，方便迁移和复用生态。
- MCP tools 第一版只读为主，还是允许受控发起实验。
