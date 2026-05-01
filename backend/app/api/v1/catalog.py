from __future__ import annotations

from fastapi import APIRouter

from app.core.config import settings
from app.observability import langfuse_enabled
from app.schemas.agents import AgentTypeInfo
from app.schemas.models import ProviderInfo
from app.services.catalog import agent_types, providers

router = APIRouter()


@router.get("/providers", response_model=list[ProviderInfo])
async def list_providers() -> list[ProviderInfo]:
    return providers()


@router.get("/agent-types", response_model=list[AgentTypeInfo])
async def list_agent_types() -> list[AgentTypeInfo]:
    return agent_types()


@router.get("/langfuse-config")
async def get_langfuse_config() -> dict:
    return {
        "enabled": langfuse_enabled(),
        "host": settings.langfuse_host if langfuse_enabled() else None,
    }

