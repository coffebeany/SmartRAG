import json

from fastapi.testclient import TestClient

from app.agent_actions import action_registry, list_action_specs
from app.main import create_app


def test_agent_action_registry_has_unique_serializable_specs() -> None:
    specs = list_action_specs()
    names = [spec.name for spec in specs]

    assert len(specs) >= 60
    assert len(names) == len(set(names))
    assert "list_material_batches" in names
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


def test_mcp_route_is_mounted() -> None:
    app = create_app()

    assert any(getattr(route, "path", None) == "/mcp" for route in app.routes)
