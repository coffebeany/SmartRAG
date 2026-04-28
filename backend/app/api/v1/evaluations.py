from __future__ import annotations

from fastapi import APIRouter, status

from app.schemas.evaluations import ParseEvaluationRunCreate, ParseEvaluatorOut
from app.services import evaluations as evaluation_service

router = APIRouter()


@router.get("/parse-evaluators", response_model=list[ParseEvaluatorOut])
async def list_parse_evaluators() -> list[ParseEvaluatorOut]:
    return await evaluation_service.list_parse_evaluators()


@router.post("/parse-evaluation-runs", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def create_parse_evaluation_run(payload: ParseEvaluationRunCreate) -> None:
    await evaluation_service.create_parse_evaluation_run(payload)
