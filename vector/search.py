"""
Semantic Search — query the vector store with natural language
"""

from typing import List, Dict, Optional
from vector.embedder import Embedder
from vector.store import VectorStore
import logging

logger = logging.getLogger(__name__)


class SemanticSearch:
    def __init__(self):
        self.embedder = Embedder()
        self.store = VectorStore()

    async def search(self, query: str, top_k: int = 10, min_score: float = 0.5) -> List[Dict]:
        """
        Embed query → similarity search in Qdrant → return ranked results.
        """
        vector = await self.embedder.embed(query)
        results = await self.store.search(vector, top_k=top_k * 2)  # over-fetch, then filter

        # Filter by minimum similarity score
        filtered = [r for r in results if r.get("_score", 0) >= min_score]

        # Deduplicate by URL
        seen_urls: set = set()
        unique = []
        for r in filtered:
            url = r.get("url", "")
            if url not in seen_urls:
                seen_urls.add(url)
                unique.append(r)

        return unique[:top_k]

    async def index_page(self, url: str, title: str, content: str):
        """Chunk a page and index all chunks into the vector store."""
        from vector.embedder import chunk_text
        import hashlib

        chunks = chunk_text(content)
        vectors = await self.embedder.embed_batch(chunks)

        for i, (chunk, vector) in enumerate(zip(chunks, vectors)):
            doc_id = hashlib.md5(f"{url}_{i}".encode()).hexdigest()
            await self.store.upsert(
                doc_id=doc_id,
                vector=vector,
                payload={"url": url, "title": title, "chunk_index": i, "text": chunk},
            )

        logger.info(f"Indexed {len(chunks)} chunks for {url}")
