"""
Embedder — free NVIDIA Nemotron embedding model via OpenRouter
Model: nvidia/llama-nemotron-embed-vl-1b-v2:free
Dims:  1024
Cost:  $0
"""

import httpx
import asyncio
from typing import List
from config import settings
import logging

logger = logging.getLogger(__name__)

CHUNK_SIZE    = settings.indexer_chunk_size
CHUNK_OVERLAP = settings.indexer_chunk_overlap
BATCH_SIZE    = settings.indexer_batch_size


class Embedder:
    def __init__(self):
        if not settings.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY not set")
        self.api_key = settings.openrouter_api_key
        self.model   = settings.embedding_model
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type":  "application/json",
            "HTTP-Referer":  "https://ultrasearch.app",
            "X-Title":       "Ultra Search Engine",
        }

    async def embed(self, text: str) -> List[float]:
        """Embed a single text string."""
        results = await self.embed_batch([text])
        return results[0]

    async def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Embed a batch of texts.
        OpenRouter free tier is rate-limited so we chunk into BATCH_SIZE
        and add a tiny backoff on 429s.
        """
        all_embeddings: List[List[float]] = []

        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i : i + BATCH_SIZE]
            embeddings = await self._call_api(batch)
            all_embeddings.extend(embeddings)

            # Small polite pause between batches to respect rate limits
            if i + BATCH_SIZE < len(texts):
                await asyncio.sleep(0.1)

        return all_embeddings

    async def _call_api(self, texts: List[str], retry: int = 0) -> List[List[float]]:
        payload = {"model": self.model, "input": texts}

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{settings.openrouter_base_url}/embeddings",
                headers=self._headers,
                json=payload,
            )

            # Free tier rate limit — back off and retry up to 3 times
            if resp.status_code == 429 and retry < 3:
                wait = 2 ** retry
                logger.warning(f"Embedding rate limited, retrying in {wait}s …")
                await asyncio.sleep(wait)
                return await self._call_api(texts, retry + 1)

            resp.raise_for_status()
            data = resp.json()

        # OpenRouter returns data sorted by index
        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """
    Split text into overlapping word-based chunks.
    Returns empty list for empty input.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    start  = 0
    step   = max(1, chunk_size - overlap)

    while start < len(words):
        end = start + chunk_size
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start += step

    return chunks
