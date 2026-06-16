"""
BM25 — PostgreSQL full-text search over the pages table.
Uses the tsvector column populated by the DB trigger in models.py.
Returns results ranked by ts_rank_cd (cover density ranking).
"""

from typing import List, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


class BM25Search:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def search(
        self,
        query: str,
        top_k: int = 50,
        domain_filter: Optional[str] = None,
    ) -> List[Dict]:
        """
        Full-text search using PostgreSQL tsvector + plainto_tsquery.
        Returns list of dicts with url, title, snippet, bm25_rank, domain.
        """
        if not query.strip():
            return []

        domain_clause = "AND domain = :domain" if domain_filter else ""

        sql = text(f"""
            SELECT
                url,
                domain,
                title,
                ts_rank_cd(search_vector, query, 32) AS rank,
                ts_headline(
                    'english',
                    coalesce(content, ''),
                    query,
                    'MaxWords=40, MinWords=20, ShortWord=3,
                     HighlightAll=false, MaxFragments=2,
                     FragmentDelimiter=\" … \"'
                ) AS snippet
            FROM pages, plainto_tsquery('english', :query) query
            WHERE search_vector @@ query
              AND search_vector IS NOT NULL
              {domain_clause}
            ORDER BY rank DESC
            LIMIT :top_k
        """)

        params = {"query": query, "top_k": top_k}
        if domain_filter:
            params["domain"] = domain_filter

        try:
            result = await self.session.execute(sql, params)
            rows = result.fetchall()
        except Exception as e:
            logger.warning(f"BM25 search failed: {e}")
            return []

        return [
            {
                "url":       row.url,
                "domain":    row.domain,
                "title":     row.title or "",
                "snippet":   _strip_highlight_tags(row.snippet or ""),
                "bm25_rank": float(row.rank),
            }
            for row in rows
        ]


def _strip_highlight_tags(text: str) -> str:
    """Remove PostgreSQL ts_headline <b> tags for clean output."""
    return text.replace("<b>", "").replace("</b>", "")
