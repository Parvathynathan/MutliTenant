import uuid
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models

from .config import COLLECTION_NAME, VECTOR_DIMENSION


class QdrantStore:
    def __init__(self, storage_dir: Path, collection_name: str = COLLECTION_NAME) -> None:
        self.client = QdrantClient(path=str(storage_dir))
        self.collection_name = collection_name
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(self.collection_name):
            return
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=VECTOR_DIMENSION,
                distance=models.Distance.COSINE,
            ),
        )
        self.client.create_payload_index(
            collection_name=self.collection_name,
            field_name="tenant_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )

    def tenant_filter(self, tenant_id: str) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(
                    key="tenant_id",
                    match=models.MatchValue(value=tenant_id),
                )
            ]
        )

    def upsert_chunks(
        self,
        tenant_id: str,
        filename: str,
        chunks: list[str],
        embeddings: list[list[float]],
    ) -> int:
        points = [
            models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "tenant_id": tenant_id,
                    "filename": filename,
                    "text": chunk,
                },
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]
        if points:
            self.client.upsert(collection_name=self.collection_name, points=points)
        return len(points)

    def search(self, tenant_id: str, query_vector: list[float], limit: int):
        return self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=self.tenant_filter(tenant_id),
            limit=limit,
        ).points




    