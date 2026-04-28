from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.core.config import settings

VectorDBStatus = Literal["available", "missing_dependency", "adapter_only", "needs_config"]


@dataclass(frozen=True)
class VectorDBAvailability:
    status: VectorDBStatus
    reason: str


@dataclass(frozen=True)
class VectorDBSpec:
    vectordb_name: str
    display_name: str
    description: str
    db_type: str
    capabilities: tuple[str, ...]
    config_schema: dict
    default_config: dict = field(default_factory=dict)
    advanced_options_schema: dict = field(default_factory=dict)
    source: str = "built_in"
    enabled: bool = True
    required_dependencies: tuple[str, ...] = ()
    default_storage_uri: str | None = None
    adapter_status: VectorDBStatus = "available"
    adapter_reason: str | None = None

    def availability(self) -> VectorDBAvailability:
        if self.adapter_status != "available":
            return VectorDBAvailability(
                self.adapter_status,
                self.adapter_reason or f"{self.display_name} adapter is not executable yet.",
            )
        missing = [
            dependency
            for dependency in self.required_dependencies
            if importlib.util.find_spec(dependency) is None
        ]
        if missing:
            return VectorDBAvailability(
                "missing_dependency",
                f"Missing Python dependency: {', '.join(missing)}.",
            )
        return VectorDBAvailability("available", "VectorDB adapter is available.")


class VectorDBRegistry:
    def __init__(self) -> None:
        self._items: dict[str, VectorDBSpec] = {}
        self._register_defaults()

    def register(self, spec: VectorDBSpec) -> None:
        self._items[spec.vectordb_name] = spec

    def get(self, vectordb_name: str) -> VectorDBSpec | None:
        return self._items.get(vectordb_name)

    def list_enabled(self) -> list[VectorDBSpec]:
        return [item for item in self._items.values() if item.enabled]

    def _register_defaults(self) -> None:
        vector_root = Path(settings.vector_storage_root)
        chroma_path = str(vector_root / "chroma")
        qdrant_path = str(vector_root / "qdrant")
        metric_schema = {
            "type": "string",
            "enum": ["cosine", "l2", "ip"],
            "description": "Similarity metric used by the vector index.",
        }
        embedding_batch_schema = {
            "type": "integer",
            "minimum": 1,
            "maximum": 1000,
            "description": "Number of vectors to upsert in one adapter batch.",
        }
        common_advanced = {
            "type": "object",
            "properties": {
                "similarity_metric": metric_schema,
                "embedding_batch": embedding_batch_schema,
                "normalize_embeddings": {
                    "type": "boolean",
                    "description": "Normalize embedding vectors before writing to VectorDB.",
                },
                "metadata_mode": {
                    "type": "string",
                    "enum": ["full", "minimal"],
                    "description": "How much chunk/file metadata should be stored as vector payload.",
                },
                "payload_fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional payload field allow-list for VectorDB metadata.",
                },
            },
        }
        self.register(
            VectorDBSpec(
                vectordb_name="chroma",
                display_name="Chroma",
                description="Local persistent Chroma VectorDB for default SmartRAG experiments.",
                db_type="chroma",
                capabilities=("local", "persistent", "metadata_payload", "delete_collection"),
                required_dependencies=("chromadb",),
                default_storage_uri=chroma_path,
                config_schema={
                    "type": "object",
                    "properties": {
                        "client_type": {"type": "string", "enum": ["persistent"], "default": "persistent"},
                        "path": {"type": "string", "default": chroma_path},
                        "collection_name": {"type": "string"},
                        "similarity_metric": metric_schema,
                    },
                },
                advanced_options_schema=common_advanced
                | {
                    "properties": common_advanced["properties"]
                    | {
                        "hnsw_config": {
                            "type": "object",
                            "description": "Chroma HNSW metadata options, passed through where supported.",
                        }
                    }
                },
                default_config={
                    "client_type": "persistent",
                    "path": chroma_path,
                    "similarity_metric": "cosine",
                    "embedding_batch": 100,
                    "normalize_embeddings": False,
                    "metadata_mode": "full",
                },
            )
        )
        self.register(
            VectorDBSpec(
                vectordb_name="qdrant",
                display_name="Qdrant",
                description="Qdrant vector database adapter for local path or remote service usage.",
                db_type="qdrant",
                capabilities=("local", "remote", "metadata_payload", "delete_collection"),
                required_dependencies=("qdrant_client",),
                default_storage_uri=qdrant_path,
                config_schema={
                    "type": "object",
                    "properties": {
                        "client_type": {"type": "string", "enum": ["local", "remote"], "default": "local"},
                        "path": {"type": "string", "default": qdrant_path},
                        "url": {"type": "string"},
                        "api_key": {"type": "string"},
                        "collection_name": {"type": "string"},
                        "similarity_metric": metric_schema,
                    },
                },
                advanced_options_schema=common_advanced
                | {
                    "properties": common_advanced["properties"]
                    | {
                        "hnsw_config": {"type": "object"},
                        "quantization_config": {"type": "object"},
                    }
                },
                default_config={
                    "client_type": "local",
                    "path": qdrant_path,
                    "similarity_metric": "cosine",
                    "embedding_batch": 100,
                    "normalize_embeddings": False,
                    "metadata_mode": "full",
                },
            )
        )
        self.register(
            VectorDBSpec(
                vectordb_name="pgvector",
                display_name="pgvector",
                description="PostgreSQL pgvector adapter using the configured SmartRAG database.",
                db_type="pgvector",
                capabilities=("postgres", "metadata_payload", "delete_collection"),
                default_storage_uri="postgresql://configured-database/vector_store_items",
                config_schema={
                    "type": "object",
                    "properties": {
                        "collection_name": {"type": "string"},
                        "database_url": {"type": "string"},
                        "similarity_metric": metric_schema,
                    },
                },
                advanced_options_schema=common_advanced
                | {
                    "properties": common_advanced["properties"]
                    | {"index_type": {"type": "string", "enum": ["hnsw", "ivfflat", "none"]}}
                },
                default_config={
                    "similarity_metric": "cosine",
                    "embedding_batch": 100,
                    "normalize_embeddings": False,
                    "metadata_mode": "full",
                    "index_type": "none",
                },
            )
        )
        for name in ["milvus", "weaviate", "pinecone", "couchbase"]:
            self.register(
                VectorDBSpec(
                    vectordb_name=name,
                    display_name=name.title(),
                    description=f"AutoRAG-compatible {name.title()} VectorDB adapter placeholder.",
                    db_type=name,
                    capabilities=("remote", "metadata_payload"),
                    config_schema={"type": "object", "properties": {"collection_name": {"type": "string"}}},
                    advanced_options_schema=common_advanced,
                    default_config={"similarity_metric": "cosine", "embedding_batch": 100},
                    adapter_status="adapter_only",
                    adapter_reason="Registry metadata is available; executable adapter will be added later.",
                )
            )


vectordb_registry = VectorDBRegistry()
