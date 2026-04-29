import json
from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.agent_actions import AgentActionContext, action_registry, execute_action, list_action_specs
from app.agent_actions.registry import smartrag_action
from app.agent_actions.actions import _parse_tool_hint, _vector_tool_hint
from app.main import create_app
from app.services import smartrag_agent
from app.services.smartrag_agent import SMART_RAG_AGENT_RECURSION_LIMIT, _agent_profile_summary, _model_summary


def test_agent_action_registry_has_unique_serializable_specs() -> None:
    specs = list_action_specs()
    names = [spec.name for spec in specs]

    assert len(specs) >= 60
    assert len(names) == len(set(names))
    assert "list_material_batches" in names
    assert "list_model_connections" in names
    assert "list_agent_profiles" in names
    assert "get_rag_flow_build_guide" in names
    assert "run_rag_flow" in names
    assert "get_evaluation_failure_cases" in names
    for spec in specs:
        assert spec.description
        assert "Side effects:" in spec.description
        json.dumps(spec.input_schema)
        json.dumps(spec.output_schema)


def test_agent_action_descriptions_mark_destructive_tools() -> None:
    destructive = [action for action in action_registry.list() if action.is_destructive]
    read_only = action_registry.get("list_material_batches")

    assert destructive
    assert all("destructive write operation" in action.description for action in destructive)
    assert "read-only" in read_only.description


def test_agent_actions_api_returns_registry_metadata() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/agent-actions")

    assert response.status_code == 200
    by_name = {item["name"]: item for item in response.json()}
    assert by_name["create_parse_run"]["permission_scope"] == "parse:write"
    assert by_name["delete_vector_run"]["is_destructive"] is True
    assert "batch_id" in by_name["get_parse_plan"]["input_schema"]["properties"]
    assert "agent_id" in by_name["get_agent_profile"]["input_schema"]["properties"]
    assert "answer_generator" in by_name["create_rag_flow"]["description"]
    assert "passage_reranker" in by_name["create_component_config"]["description"]


def test_rag_and_agent_profile_action_descriptions_are_llm_explicit() -> None:
    guide = action_registry.get("get_rag_flow_build_guide")
    create_flow = action_registry.get("create_rag_flow")
    create_config = action_registry.get("create_component_config")
    list_agents = action_registry.get("list_agent_profiles")

    assert "answer_generator" in guide.description
    assert "Agent Profile" in guide.description
    assert "agent_id" in create_flow.description
    assert "model_id" in create_flow.description
    assert "passage_reranker" in create_config.description
    assert "answer_generator" in create_config.description
    assert "AgentProfile is not the same as ModelConnection" in list_agents.description


def test_smartrag_agent_recursion_limit_is_raised_for_tool_loops() -> None:
    assert SMART_RAG_AGENT_RECURSION_LIMIT == 200


def test_mcp_route_is_mounted() -> None:
    app = create_app()

    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)


def test_agent_tool_recoverable_error_hints_point_to_observation_tools() -> None:
    assert "get_parse_plan" in _parse_tool_hint("Unknown parser")
    assert "list_parser_strategies" in _parse_tool_hint("Unknown parser")
    assert "list_model_connections" in _vector_tool_hint("Model not found")
    assert "不要编造外部模型名称" in _vector_tool_hint("Model not found")


def test_execute_action_unwraps_arguments_dict_and_json_string() -> None:
    class EchoInput(BaseModel):
        value: str

    name = "test_echo_arguments_wrapper"
    if name not in {action.name for action in action_registry.list()}:
        @smartrag_action(name=name, title="Test echo", input_model=EchoInput)
        async def echo_action(ctx: AgentActionContext, payload: EchoInput) -> dict[str, str]:
            return {"value": payload.value}

    async def run_cases():
        ctx = AgentActionContext(session=None)  # type: ignore[arg-type]
        first = await execute_action(name, {"arguments": {"value": "dict"}}, ctx)
        second = await execute_action(name, {"arguments": "{\"value\":\"json\"}"}, ctx)
        third = await execute_action(name, {"arguments": "not-json"}, ctx)
        return first, second, third

    import asyncio

    first, second, third = asyncio.run(run_cases())

    assert first.ok is True
    assert first.output == {"value": "dict"}
    assert second.ok is True
    assert second.output == {"value": "json"}
    assert third.ok is False
    assert "Do not wrap tool arguments" in (third.error or "")


def test_model_summary_excludes_secret_fields() -> None:
    class Model:
        model_id = "model-1"
        display_name = "Embedding"
        provider = "openai_compatible"
        model_name = "BAAI/bge"
        model_category = "embedding"
        enabled = True
        connection_status = "available"
        supports_tools = None
        api_key_encrypted = "secret"

    summary = _model_summary(Model())

    assert summary["model_id"] == "model-1"
    assert summary["model_category"] == "embedding"
    assert "api_key_encrypted" not in summary
    assert "secret" not in json.dumps(summary)


def test_agent_profile_summary_excludes_prompt_and_secret_data() -> None:
    class Agent:
        agent_id = "agent-1"
        agent_name = "Answer Agent"
        agent_type = "custom"
        model_id = "model-1"
        dry_run_status = "available"
        enabled = True
        prompt_template = "secret prompt"

    summary = _agent_profile_summary(Agent())

    assert summary["agent_id"] == "agent-1"
    assert summary["model_id"] == "model-1"
    assert "prompt_template" not in summary
    assert "secret prompt" not in json.dumps(summary)


def test_iter_agent_events_starts_after_sequence(monkeypatch) -> None:
    rows_by_call = [
        [
            SimpleNamespace(
                event_id="event-2",
                run_id="run-1",
                event_type="message_delta",
                sequence=2,
                payload={"content": "two"},
                created_at=datetime.now(UTC),
            )
        ],
        [],
    ]

    class ScalarResult:
        def __init__(self, rows):
            self.rows = rows

        def all(self):
            return self.rows

    class Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def scalars(self, statement):
            return ScalarResult(rows_by_call.pop(0))

    async def fake_get_agent_run_model(session, run_id):
        return SimpleNamespace(status="completed")

    monkeypatch.setattr(smartrag_agent, "AsyncSessionLocal", lambda: Session())
    monkeypatch.setattr(smartrag_agent, "get_agent_run_model", fake_get_agent_run_model)

    async def collect():
        events = []
        async for event in smartrag_agent.iter_agent_events("run-1", after_sequence=1):
            events.append(event)
        return events

    import asyncio

    events = asyncio.run(collect())

    assert len(events) == 1
    assert "event: message_delta" in events[0]
    assert '"sequence": 2' in events[0]


def test_chroma_client_disables_anonymized_telemetry(monkeypatch, tmp_path) -> None:
    from app.vectorstores.adapters import ChromaVectorStoreAdapter

    captured = {}

    def fake_persistent_client(**kwargs):
        captured.update(kwargs)
        return object()

    import chromadb

    monkeypatch.setattr(chromadb, "PersistentClient", fake_persistent_client)

    ChromaVectorStoreAdapter()._client({"path": str(tmp_path / "chroma")})

    assert captured["path"] == str(tmp_path / "chroma")
    assert captured["settings"].anonymized_telemetry is False
