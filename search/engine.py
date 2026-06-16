"""
Search Engine — queries your PostgreSQL index via BM25 full-text search.
No vector DB, no embedding API calls.

Pipeline:
  1. BM25 search  (PostgreSQL FTS tsvector)
  2. Return ranked results directly
"""

import logging
from typing import List, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from search.bm25 import BM25Search
from config      import settings

logger = logging.getLogger(__name__)


class SearchEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.bm25    = BM25Search(session)

    async def search(
        self,
        query:         str,
        top_k:         int           = 10,
        domain_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        BM25 full-text search against PostgreSQL.
        Returns up to top_k results ranked by ts_rank_cd score.
        """
        if not query.strip():
            return []

        bm25_results = await self.bm25.search(
            query,
            top_k=top_k,
            domain_filter=domain_filter,
        )

        # Normalise fields so the API layer has a consistent shape.
        results = []
        for rank, r in enumerate(bm25_results, start=1):
            results.append({
                "url":      r["url"],
                "title":    r.get("title", ""),
                "domain":   r.get("domain", ""),
                "snippet":  r.get("snippet", ""),
                "score":    r.get("bm25_rank", 0.0),
                "in_bm25":  True,
                # Kept for API response-model compatibility; always False now.
                "in_vector": False,
            })

        return results

    async def index_stats(self) -> Dict:
        """Return index health stats."""
        from sqlalchemy import text
        result = await self.session.execute(
            text("SELECT COUNT(*) as pages, MAX(crawled_at) as last_crawl FROM pages")
        )
        row = result.fetchone()
        return {
            "total_pages": row.pages if row else 0,
            "last_crawl":  str(row.last_crawl) if row and row.last_crawl else None,
        }
