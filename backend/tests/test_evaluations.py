import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.evaluations import ParseEvaluationRunCreate
from app.services.evaluations import create_parse_evaluation_run, list_parse_evaluators


@pytest.mark.asyncio
async def test_parse_evaluators_are_registered_as_placeholders() -> None:
    evaluators = await list_parse_evaluators()

    by_name = {evaluator.evaluator_name: evaluator for evaluator in evaluators}
    assert {"parsebench", "score_bench"}.issubset(by_name)
    assert by_name["parsebench"].availability_status == "adapter_only"
    assert by_name["score_bench"].availability_status == "adapter_only"


@pytest.mark.asyncio
async def test_create_parse_evaluation_run_is_not_implemented() -> None:
    payload = ParseEvaluationRunCreate(
        batch_id="batch-1",
        parse_run_id="run-1",
        evaluator_name="parsebench",
        evaluator_config={},
    )

    with pytest.raises(HTTPException) as exc_info:
        await create_parse_evaluation_run(payload)

    assert exc_info.value.status_code == 501


def test_parse_evaluator_api_returns_placeholders() -> None:
    client = TestClient(create_app())

    response = client.get("/api/v1/parse-evaluators")

    assert response.status_code == 200
    by_name = {item["evaluator_name"]: item for item in response.json()}
    assert by_name["parsebench"]["availability_status"] == "adapter_only"
    assert by_name["score_bench"]["availability_status"] == "adapter_only"


def test_parse_evaluation_run_api_returns_501() -> None:
    client = TestClient(create_app())

    response = client.post(
        "/api/v1/parse-evaluation-runs",
        json={
            "batch_id": "batch-1",
            "parse_run_id": "run-1",
            "evaluator_name": "parsebench",
            "evaluator_config": {},
        },
    )

    assert response.status_code == 501
