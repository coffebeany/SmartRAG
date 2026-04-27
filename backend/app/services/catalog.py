from __future__ import annotations

from pathlib import Path

from app.schemas.agents import AgentTypeInfo
from app.schemas.models import ProviderInfo

PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

DEFAULT_AGENT_SCHEMAS: dict[str, dict] = {
    "custom": {},
    "query_rewrite": {"query": "string"},
    "query_compress": {"query": "string"},
    "multi_query": {"semantic_queries": "list[string]"},
    "query_decompose": {"semantic_queries": "list[string]", "metadata_filter": "object"},
    "hyde": {"hypothetical_document": "string"},
    "metadata_extraction": {"metadata_filter": "object"},
    "routing": {"route": "string"},
    "failure_analysis": {"analysis": "string", "suggestions": "list[string]"},
    "strategy_planner": {"strategy": "object"},
    "llm_judge": {"score": "number", "reason": "string"},
}


def default_prompt(agent_type: str) -> str:
    if agent_type == "custom":
        return ""
    prompt_path = PROMPTS_DIR / agent_type / "default.md"
    if prompt_path.exists():
        return prompt_path.read_text(encoding="utf-8")
    return "Process the following input.\n\n{query}"


def default_output_schema(agent_type: str) -> dict:
    return DEFAULT_AGENT_SCHEMAS.get(agent_type, {})


def providers() -> list[ProviderInfo]:
    return [
        ProviderInfo(provider="openai_compatible", display_name="OpenAI Compatible", default_base_url="https://api.openai.com/v1", supports_categories=["llm", "embedding", "reasoning", "reranker", "custom"]),
        ProviderInfo(provider="ollama", display_name="Ollama", default_base_url="http://127.0.0.1:11434", supports_categories=["llm", "embedding"]),
        ProviderInfo(provider="custom", display_name="Custom HTTP Service", default_base_url="", supports_categories=["custom", "reranker"]),
    ]


def agent_types() -> list[AgentTypeInfo]:
    return [
        AgentTypeInfo(
            agent_type=agent_type,
            display_name=agent_type.replace("_", " ").title(),
            default_prompt=default_prompt(agent_type),
            output_schema=schema,
        )
        for agent_type, schema in DEFAULT_AGENT_SCHEMAS.items()
    ]
