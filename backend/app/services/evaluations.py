from __future__ import annotations

from fastapi import HTTPException, status

from app.evaluators.registry import ParseEvaluatorSpec, parse_evaluator_registry
from app.schemas.evaluations import ParseEvaluationRunCreate, ParseEvaluatorOut


def parse_evaluator_out(evaluator: ParseEvaluatorSpec) -> ParseEvaluatorOut:
    availability = evaluator.availability()
    return ParseEvaluatorOut(
        evaluator_name=evaluator.evaluator_name,
        display_name=evaluator.display_name,
        description=evaluator.description,
        capabilities=list(evaluator.capabilities),
        config_schema=evaluator.config_schema,
        default_config=evaluator.default_config,
        source=evaluator.source,
        enabled=evaluator.enabled,
        availability_status=availability.status,
        availability_reason=availability.reason,
    )


async def list_parse_evaluators() -> list[ParseEvaluatorOut]:
    return [
        parse_evaluator_out(evaluator)
        for evaluator in parse_evaluator_registry.list_enabled()
    ]


async def create_parse_evaluation_run(payload: ParseEvaluationRunCreate) -> None:
    evaluator = parse_evaluator_registry.get(payload.evaluator_name)
    if not evaluator:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown parse evaluator: {payload.evaluator_name}",
        )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Parse quality evaluation execution is not connected yet.",
    )
