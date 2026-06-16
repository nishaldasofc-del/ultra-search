"""
Vector Store — Qdrant wrapper, 1024-dim (free NVIDIA embedding model)
"""

from typing import List, Dict, Optional
from config import settings
import logging

logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self):
        from qdrant_client import QdrantClient
        self.client     = QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
        self.collection = settings.qdrant_collection
        self._ensure_collection()

    def _ensure_collection(self):
        from qdrant_client.models import Distance, VectorParams
        existing = [c.name for c in self.client.get_collections().collections]
        if self.collection not in existing:
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(
                    size=settings.embedding_dim,   # 1024
                    distance=Distance.COSINE,
                ),
            )
            logger.info(f"Created Qdrant collection '{self.collection}' dim={settings.embedding_dim}")

    async def upsert(self, doc_id: str, vector: List[float], payload: Dict):
        from qdrant_client.models import PointStruct
        self.client.upsert(
            collection_name=self.collection,
            points=[PointStruct(id=doc_id, vector=vector, payload=payload)],
        )

    async def upsert_batch(self, points: List[Dict]):
        """
        Bulk upsert for indexing pipeline.
        points: list of {doc_id, vector, payload}
        """
        from qdrant_client.models import PointStruct
        structs = [
            PointStruct(id=p["doc_id"], vector=p["vector"], payload=p["payload"])
            for p in points
        ]
        self.client.upsert(collection_name=self.collection, points=structs)

    async def search(
        self,
        vector: List[float],
        top_k: int = 50,
        domain_filter: Optional[str] = None,
    ) -> List[Dict]:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        query_filter = None
        if domain_filter:
            query_filter = Filter(
                must=[FieldCondition(key="domain", match=MatchValue(value=domain_filter))]
            )

        results = self.client.search(
            collection_name=self.collection,
            query_vector=vector,
            limit=top_k,
            with_payload=True,
            query_filter=query_filter,
        )
        return [{**r.payload, "_score": r.score, "_id": r.id} for r in results]

    async def delete_by_url(self, url: str):
        """Remove all chunks belonging to a URL."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        self.client.delete(
            collection_name=self.collection,
            points_selector=Filter(
                must=[FieldCondition(key="url", match=MatchValue(value=url))]
            ),
        )

    def count(self) -> int:
        info = self.client.get_collection(self.collection)
        return info.points_count
