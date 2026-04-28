from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field


@dataclass(frozen=True)
class ParseEvaluatorAvailability:
    status: str
    reason: str


@dataclass(frozen=True)
class ParseEvaluatorSpec:
    evaluator_name: str
    display_name: str
    description: str
    capabilities: tuple[str, ...]
    config_schema: dict = field(default_factory=dict)
    default_config: dict = field(default_factory=dict)
    source: str = "built_in"
    enabled: bool = True
    executable: bool = False

    def availability(self) -> ParseEvaluatorAvailability:
        if not self.enabled:
            return ParseEvaluatorAvailability("disabled", "Evaluator is disabled.")
        if not self.executable:
            return ParseEvaluatorAvailability(
                "adapter_only",
                "Registered for API compatibility; executable evaluator adapter is pending.",
            )
        return ParseEvaluatorAvailability("available", "Available")


class ParseEvaluatorRegistry:
    def __init__(self) -> None:
        self._evaluators: dict[str, ParseEvaluatorSpec] = {}

    def register(self, evaluator: ParseEvaluatorSpec) -> None:
        self._evaluators[evaluator.evaluator_name] = evaluator

    def get(self, evaluator_name: str) -> ParseEvaluatorSpec | None:
        return self._evaluators.get(evaluator_name)

    def list_enabled(self) -> list[ParseEvaluatorSpec]:
        return sorted(
            [evaluator for evaluator in self._evaluators.values() if evaluator.enabled],
            key=lambda evaluator: evaluator.display_name,
        )


@dataclass(frozen=True)
class EvaluationFrameworkAvailability:
    status: str
    reason: str


@dataclass(frozen=True)
class EvaluationMetricSpec:
    metric_id: str
    display_name: str
    description: str
    category: str
    requires_answer: bool = True
    requires_ground_truth: bool = True
    requires_contexts: bool = True


@dataclass(frozen=True)
class EvaluationFrameworkSpec:
    framework_id: str
    display_name: str
    description: str
    source: str
    default_metrics: tuple[str, ...]
    metrics: tuple[EvaluationMetricSpec, ...]
    generator_config_schema: dict = field(default_factory=dict)
    default_generator_config: dict = field(default_factory=dict)
    required_dependencies: tuple[str, ...] = ()
    optional_dependency_extra: str | None = None
    executable: bool = True

    def availability(self) -> EvaluationFrameworkAvailability:
        if not self.executable:
            return EvaluationFrameworkAvailability("adapter_only", "Framework adapter is registered but not executable.")
        missing = []
        for dependency in self.required_dependencies:
            try:
                found = importlib.util.find_spec(dependency) is not None
            except ModuleNotFoundError:
                found = False
            if not found:
                missing.append(dependency)
        if missing:
            return EvaluationFrameworkAvailability(
                "missing_dependency",
                f"Missing Python dependencies: {', '.join(missing)}",
            )
        return EvaluationFrameworkAvailability("available", "Available")


class EvaluationFrameworkRegistry:
    def __init__(self) -> None:
        self._frameworks: dict[str, EvaluationFrameworkSpec] = {}

    def register(self, framework: EvaluationFrameworkSpec) -> None:
        self._frameworks[framework.framework_id] = framework

    def get(self, framework_id: str) -> EvaluationFrameworkSpec | None:
        return self._frameworks.get(framework_id)

    def list(self) -> list[EvaluationFrameworkSpec]:
        return sorted(self._frameworks.values(), key=lambda framework: framework.display_name)


def schema(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


parse_evaluator_registry = ParseEvaluatorRegistry()
evaluation_framework_registry = EvaluationFrameworkRegistry()

parse_evaluator_registry.register(
    ParseEvaluatorSpec(
        evaluator_name="parsebench",
        display_name="ParseBench",
        description=(
            "Placeholder adapter for ParseBench-style parser benchmark evaluation. "
            "Execution is not connected in this version."
        ),
        capabilities=(
            "tables",
            "charts",
            "content_faithfulness",
            "semantic_formatting",
            "visual_grounding",
        ),
        config_schema=schema(
            {
                "group": {
                    "type": "string",
                    "enum": ["all", "table", "chart", "layout", "text_content", "text_formatting"],
                },
                "test_mode": {"type": "boolean"},
            }
        ),
        default_config={"group": "all", "test_mode": True},
        source="parsebench",
        executable=False,
    )
)

evaluation_framework_registry.register(
    EvaluationFrameworkSpec(
        framework_id="ragas",
        display_name="RAGAS",
        description="RAGAS-compatible testset generation and RAG evaluation adapter.",
        source="ragas",
        default_metrics=("context_precision", "context_recall", "faithfulness", "answer_relevancy"),
        metrics=(
            EvaluationMetricSpec(
                metric_id="context_precision",
                display_name="Context Precision",
                description="Measures whether retrieved contexts are relevant and ranked before irrelevant contexts.",
                category="retrieval",
            ),
            EvaluationMetricSpec(
                metric_id="context_recall",
                display_name="Context Recall",
                description="Measures whether retrieved contexts contain information needed by the reference answer.",
                category="retrieval",
            ),
            EvaluationMetricSpec(
                metric_id="faithfulness",
                display_name="Faithfulness",
                description="Measures factual consistency between the generated answer and retrieved contexts.",
                category="generation",
            ),
            EvaluationMetricSpec(
                metric_id="answer_relevancy",
                display_name="Answer Relevancy",
                description="Measures whether the generated answer addresses the question.",
                category="generation",
            ),
            EvaluationMetricSpec(
                metric_id="source_chunk_hit@3",
                display_name="Source Chunk Hit@3",
                description="Checks whether any source chunk used to generate the eval item appears in the top 3 retrieved chunks.",
                category="retrieval_id",
                requires_answer=False,
                requires_ground_truth=False,
                requires_contexts=False,
            ),
            EvaluationMetricSpec(
                metric_id="source_chunk_hit@5",
                display_name="Source Chunk Hit@5",
                description="Checks whether any source chunk used to generate the eval item appears in the top 5 retrieved chunks.",
                category="retrieval_id",
                requires_answer=False,
                requires_ground_truth=False,
                requires_contexts=False,
            ),
            EvaluationMetricSpec(
                metric_id="source_chunk_hit@10",
                display_name="Source Chunk Hit@10",
                description="Checks whether any source chunk used to generate the eval item appears in the top 10 retrieved chunks.",
                category="retrieval_id",
                requires_answer=False,
                requires_ground_truth=False,
                requires_contexts=False,
            ),
            EvaluationMetricSpec(
                metric_id="source_chunk_recall",
                display_name="Source Chunk Recall",
                description="Measures the proportion of source chunks that were retrieved.",
                category="retrieval_id",
                requires_answer=False,
                requires_ground_truth=False,
                requires_contexts=False,
            ),
            EvaluationMetricSpec(
                metric_id="source_chunk_mrr",
                display_name="Source Chunk MRR",
                description="Measures the reciprocal rank of the first retrieved source chunk.",
                category="retrieval_id",
                requires_answer=False,
                requires_ground_truth=False,
                requires_contexts=False,
            ),
            EvaluationMetricSpec(
                metric_id="source_chunk_rank",
                display_name="Source Chunk Rank",
                description="Records the 1-based rank position of the first retrieved source chunk.",
                category="retrieval_id",
                requires_answer=False,
                requires_ground_truth=False,
                requires_contexts=False,
            ),
        ),
        generator_config_schema=schema(
            {
                "testset_size": {"type": "integer", "title": "Testset Size", "minimum": 1, "maximum": 500},
                "language": {"type": "string", "title": "Language"},
                "query_distribution": {
                    "type": "object",
                    "title": "Query Distribution",
                    "properties": {
                        "single_hop_specific": {"type": "number", "minimum": 0, "maximum": 1},
                        "multi_hop_specific": {"type": "number", "minimum": 0, "maximum": 1},
                        "multi_hop_abstract": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                },
                "chunk_sampling": {
                    "type": "object",
                    "title": "Chunk Sampling",
                    "properties": {
                        "mode": {
                            "type": "string",
                            "enum": ["all_completed_chunks", "by_file", "top_n"],
                        },
                        "max_chunks": {"type": "integer", "minimum": 1},
                        "min_char_count": {"type": "integer", "minimum": 0},
                        "max_char_count": {"type": "integer", "minimum": 1},
                        "source_file_ids": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "persona": {"type": "string", "title": "Persona"},
                "llm_context": {"type": "string", "title": "LLM Context"},
                "random_seed": {"type": "integer", "title": "Random Seed"},
                "advanced_config": {"type": "object", "title": "Advanced Config"},
            }
        ),
        default_generator_config={
            "testset_size": 10,
            "language": "zh",
            "query_distribution": {
                "single_hop_specific": 0.7,
                "multi_hop_specific": 0.2,
                "multi_hop_abstract": 0.1,
            },
            "chunk_sampling": {"mode": "all_completed_chunks"},
            "persona": "",
            "llm_context": "",
            "advanced_config": {},
        },
        required_dependencies=("ragas", "datasets"),
        optional_dependency_extra="eval-ragas",
    )
)

parse_evaluator_registry.register(
    ParseEvaluatorSpec(
        evaluator_name="score_bench",
        display_name="SCORE-Bench",
        description=(
            "Placeholder adapter for SCORE-Bench / SCORE metric evaluation. "
            "Execution is not connected in this version."
        ),
        capabilities=(
            "content_fidelity",
            "token_recall",
            "hallucination_control",
            "table_extraction",
            "structural_understanding",
        ),
        config_schema=schema(
            {
                "metrics": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["content_fidelity", "table_extraction", "element_alignment"],
                    },
                }
            }
        ),
        default_config={"metrics": ["content_fidelity", "table_extraction", "element_alignment"]},
        source="score_bench",
        executable=False,
    )
)
