from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import asyncpg

from app.core.config import settings


@dataclass
class VectorRecord:
    vector_id: str
    text: str
    embedding: list[float]
    metadata: dict = field(default_factory=dict)


@dataclass
class VectorSearchResult:
    vector_id: str
    text: str
    score: float
    metadata: dict = field(default_factory=dict)


@dataclass
class VectorCollectionConfig:
    collection_name: str
    dimension: int
    similarity_metric: str
    storage_uri: str
    vectordb_config: dict
    index_config: dict


class VectorStoreAdapter(Protocol):
    async def health_check(self, config: dict) -> dict:
        ...

    async def ensure_collection(self, config: VectorCollectionConfig) -> None:
        ...

    async def upsert_vectors(self, config: VectorCollectionConfig, records: list[VectorRecord]) -> None:
        ...

    async def search_vectors(
        self, config: VectorCollectionConfig, query_embedding: list[float], top_k: int
    ) -> list[VectorSearchResult]:
        ...

    async def delete_collection(self, config: VectorCollectionConfig) -> None:
        ...


def _sanitize_metadata(metadata: dict) -> dict:
    clean: dict = {}
    for key, value in metadata.items():
        if value is None or isinstance(value, str | int | float | bool):
            clean[key] = value
        else:
            clean[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return clean


def _metric_for_chroma(metric: str) -> str:
    return {"cosine": "cosine", "l2": "l2", "ip": "ip"}.get(metric, "cosine")


def _metric_for_qdrant(metric: str):
    from qdrant_client.http.models import Distance

    return {"cosine": Distance.COSINE, "l2": Distance.EUCLID, "ip": Distance.DOT}.get(
        metric,
        Distance.COSINE,
    )


class ChromaVectorStoreAdapter:
    def _client(self, config: dict):
        import chromadb

        path = config.get("path") or str(Path(settings.vector_storage_root) / "chroma")
        Path(path).mkdir(parents=True, exist_ok=True)
        return chromadb.PersistentClient(path=path)

    async def health_check(self, config: dict) -> dict:
        client = self._client(config)
        client.heartbeat()
        return {"status": "available", "storage_uri": config.get("path")}

    async def ensure_collection(self, config: VectorCollectionConfig) -> None:
        client = self._client(config.vectordb_config)
        metadata = {"hnsw:space": _metric_for_chroma(config.similarity_metric)}
        hnsw_config = config.index_config.get("hnsw_config")
        if isinstance(hnsw_config, dict):
            metadata.update(hnsw_config)
        client.get_or_create_collection(name=config.collection_name, metadata=metadata)

    async def upsert_vectors(self, config: VectorCollectionConfig, records: list[VectorRecord]) -> None:
        if not records:
            return
        client = self._client(config.vectordb_config)
        collection = client.get_or_create_collection(name=config.collection_name)
        collection.upsert(
            ids=[record.vector_id for record in records],
            embeddings=[record.embedding for record in records],
            documents=[record.text for record in records],
            metadatas=[_sanitize_metadata(record.metadata) for record in records],
        )

    async def search_vectors(
        self, config: VectorCollectionConfig, query_embedding: list[float], top_k: int
    ) -> list[VectorSearchResult]:
        client = self._client(config.vectordb_config)
        collection = client.get_or_create_collection(name=config.collection_name)
        result = collection.query(
            query_embeddings=[query_embedding],
            n_results=max(top_k, 1),
            include=["documents", "metadatas", "distances"],
        )
        ids = (result.get("ids") or [[]])[0]
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        rows: list[VectorSearchResult] = []
        for index, vector_id in enumerate(ids):
            distance = float(distances[index]) if index < len(distances) else 0.0
            rows.append(
                VectorSearchResult(
                    vector_id=vector_id,
                    text=documents[index] if index < len(documents) else "",
                    score=1 / (1 + distance),
                    metadata=metadatas[index] if index < len(metadatas) and metadatas[index] else {},
                )
            )
        return rows

    async def delete_collection(self, config: VectorCollectionConfig) -> None:
        client = self._client(config.vectordb_config)
        try:
            client.delete_collection(config.collection_name)
        except Exception as exc:
            if "does not exist" not in str(exc).lower():
                raise


class QdrantVectorStoreAdapter:
    def _client(self, config: dict):
        from qdrant_client import QdrantClient

        if config.get("client_type") == "remote" or config.get("url"):
            return QdrantClient(url=config.get("url"), api_key=config.get("api_key"))
        path = config.get("path") or str(Path(settings.vector_storage_root) / "qdrant")
        Path(path).mkdir(parents=True, exist_ok=True)
        return QdrantClient(path=path)

    async def health_check(self, config: dict) -> dict:
        client = self._client(config)
        client.get_collections()
        return {"status": "available"}

    async def ensure_collection(self, config: VectorCollectionConfig) -> None:
        from qdrant_client.http.models import VectorParams

        client = self._client(config.vectordb_config)
        collections = client.get_collections().collections
        if any(item.name == config.collection_name for item in collections):
            return
        client.create_collection(
            collection_name=config.collection_name,
            vectors_config=VectorParams(
                size=config.dimension,
                distance=_metric_for_qdrant(config.similarity_metric),
            ),
        )

    async def upsert_vectors(self, config: VectorCollectionConfig, records: list[VectorRecord]) -> None:
        if not records:
            return
        from qdrant_client.http.models import PointStruct

        client = self._client(config.vectordb_config)
        client.upsert(
            collection_name=config.collection_name,
            points=[
                PointStruct(
                    id=record.vector_id,
                    vector=record.embedding,
                    payload=_sanitize_metadata(record.metadata) | {"text": record.text},
                )
                for record in records
            ],
        )

    async def search_vectors(
        self, config: VectorCollectionConfig, query_embedding: list[float], top_k: int
    ) -> list[VectorSearchResult]:
        client = self._client(config.vectordb_config)
        points = client.search(
            collection_name=config.collection_name,
            query_vector=query_embedding,
            limit=max(top_k, 1),
            with_payload=True,
        )
        rows: list[VectorSearchResult] = []
        for point in points:
            payload = dict(point.payload or {})
            text = str(payload.pop("text", "") or "")
            rows.append(
                VectorSearchResult(
                    vector_id=str(point.id),
                    text=text,
                    score=float(point.score),
                    metadata=payload,
                )
            )
        return rows

    async def delete_collection(self, config: VectorCollectionConfig) -> None:
        client = self._client(config.vectordb_config)
        collections = client.get_collections().collections
        if any(item.name == config.collection_name for item in collections):
            client.delete_collection(config.collection_name)


def _asyncpg_url(config: dict) -> str:
    value = config.get("database_url") or settings.database_url
    return value.replace("postgresql+asyncpg://", "postgresql://", 1)


class PgVectorStoreAdapter:
    async def _connection(self, config: dict):
        return await asyncpg.connect(_asyncpg_url(config))

    async def health_check(self, config: dict) -> dict:
        connection = await self._connection(config)
        try:
            await connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            return {"status": "available"}
        finally:
            await connection.close()

    async def ensure_collection(self, config: VectorCollectionConfig) -> None:
        connection = await self._connection(config.vectordb_config)
        try:
            await connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS vector_store_items (
                    collection_name text NOT NULL,
                    vector_id text NOT NULL,
                    text_content text NOT NULL,
                    embedding vector,
                    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
                    created_at timestamptz NOT NULL DEFAULT now(),
                    PRIMARY KEY (collection_name, vector_id)
                )
                """
            )
        finally:
            await connection.close()

    async def upsert_vectors(self, config: VectorCollectionConfig, records: list[VectorRecord]) -> None:
        if not records:
            return
        connection = await self._connection(config.vectordb_config)
        try:
            for record in records:
                vector_literal = "[" + ",".join(str(float(value)) for value in record.embedding) + "]"
                await connection.execute(
                    """
                    INSERT INTO vector_store_items
                        (collection_name, vector_id, text_content, embedding, metadata)
                    VALUES ($1, $2, $3, $4::vector, $5::jsonb)
                    ON CONFLICT (collection_name, vector_id)
                    DO UPDATE SET text_content = EXCLUDED.text_content,
                                  embedding = EXCLUDED.embedding,
                                  metadata = EXCLUDED.metadata
                    """,
                    config.collection_name,
                    record.vector_id,
                    record.text,
                    vector_literal,
                    json.dumps(_sanitize_metadata(record.metadata), ensure_ascii=False),
                )
        finally:
            await connection.close()

    async def search_vectors(
        self, config: VectorCollectionConfig, query_embedding: list[float], top_k: int
    ) -> list[VectorSearchResult]:
        connection = await self._connection(config.vectordb_config)
        try:
            vector_literal = "[" + ",".join(str(float(value)) for value in query_embedding) + "]"
            operator = "<#>" if config.similarity_metric == "ip" else "<=>"
            rows = await connection.fetch(
                f"""
                SELECT vector_id, text_content, metadata,
                       embedding {operator} $2::vector AS distance
                FROM vector_store_items
                WHERE collection_name = $1
                ORDER BY embedding {operator} $2::vector
                LIMIT $3
                """,
                config.collection_name,
                vector_literal,
                max(top_k, 1),
            )
            return [
                VectorSearchResult(
                    vector_id=row["vector_id"],
                    text=row["text_content"],
                    score=1 / (1 + float(row["distance"] or 0)),
                    metadata=dict(row["metadata"] or {}),
                )
                for row in rows
            ]
        finally:
            await connection.close()

    async def delete_collection(self, config: VectorCollectionConfig) -> None:
        connection = await self._connection(config.vectordb_config)
        try:
            await connection.execute(
                "DELETE FROM vector_store_items WHERE collection_name = $1",
                config.collection_name,
            )
        finally:
            await connection.close()


def get_vectorstore_adapter(vectordb_name: str) -> VectorStoreAdapter:
    if vectordb_name == "chroma":
        return ChromaVectorStoreAdapter()
    if vectordb_name == "qdrant":
        return QdrantVectorStoreAdapter()
    if vectordb_name == "pgvector":
        return PgVectorStoreAdapter()
    raise ValueError(f"VectorDB adapter is not executable: {vectordb_name}")
