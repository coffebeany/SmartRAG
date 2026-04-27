from datetime import UTC, datetime

from app.models.entities import AgentProfile
from app.services.agents import _exception_message, _to_agent_out
from app.services.catalog import agent_types, default_output_schema, default_prompt


def test_agent_out_is_flat_profile() -> None:
    now = datetime.now(UTC)
    agent = AgentProfile(
        agent_id="agent-1",
        agent_name="rewrite",
        agent_type="query_rewrite",
        model_id="model-1",
        prompt_template="Rewrite {query}",
        output_schema=default_output_schema("query_rewrite"),
        runtime_config={"temperature": 0},
        dry_run_status="unknown",
        enabled=True,
        created_at=now,
        updated_at=now,
    )

    output = _to_agent_out(agent)

    assert output.agent_id == "agent-1"
    assert output.model_id == "model-1"
    assert output.output_schema == {"query": "string"}


def test_agent_out_fills_blank_failed_dry_run_error() -> None:
    now = datetime.now(UTC)
    agent = AgentProfile(
        agent_id="agent-1",
        agent_name="rewrite",
        agent_type="query_rewrite",
        model_id="model-1",
        prompt_template="Rewrite {query}",
        output_schema=default_output_schema("query_rewrite"),
        runtime_config={"temperature": 0},
        dry_run_status="failed",
        dry_run_error="",
        enabled=True,
        created_at=now,
        updated_at=now,
    )

    output = _to_agent_out(agent)

    assert output.dry_run_error == "Unknown dry-run error"


def test_agent_types_include_custom_without_default_prompt() -> None:
    custom = next(item for item in agent_types() if item.agent_type == "custom")

    assert custom.display_name == "Custom"
    assert custom.default_prompt == ""
    assert custom.output_schema == {}
    assert default_prompt("custom") == ""


def test_agent_types_load_prompt_files() -> None:
    query_rewrite = next(item for item in agent_types() if item.agent_type == "query_rewrite")

    assert "retrieval-friendly" in query_rewrite.default_prompt
    assert query_rewrite.output_schema == {"query": "string"}


def test_exception_message_falls_back_to_class_name() -> None:
    assert _exception_message(Exception()) == "Exception"
