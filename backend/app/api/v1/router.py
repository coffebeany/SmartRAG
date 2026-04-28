from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import agents, catalog, chunks, evaluations, materials, models, rag, vectors

api_router = APIRouter()
api_router.include_router(catalog.router, tags=["catalog"])
api_router.include_router(models.router, tags=["models"])
api_router.include_router(agents.router, tags=["agent-profiles"])
api_router.include_router(materials.router, tags=["materials"])
api_router.include_router(evaluations.router, tags=["parse-evaluations"])
api_router.include_router(chunks.router, tags=["chunks"])
api_router.include_router(vectors.router, tags=["vectors"])
api_router.include_router(rag.router, tags=["rag"])
