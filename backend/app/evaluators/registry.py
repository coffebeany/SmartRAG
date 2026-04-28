from __future__ import annotations

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


def schema(properties: dict, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


parse_evaluator_registry = ParseEvaluatorRegistry()

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
