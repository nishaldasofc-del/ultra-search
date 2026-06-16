"""
Search API — POST /search
Queries your own PostgreSQL index via BM25, then live-fetches the top
results so the summarizer always works with fresh, real content.
Each live-fetched result also carries a thumbnail image URL extracted
from the page's og:image / twitter:image meta tags.
"""

import asyncio
import logging
from typing import Optional, List

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from search.engine       import SearchEngine
from database.models     import get_session
from llm.summarizer      import Summarizer
from extractor.fetcher   import ContentFetcher
from extractor.cleaner   import ContentCleaner
from extractor.parser    import ContentParser

router = APIRouter()
logger = logging.getLogger(__name__)

# How many top results to live-fetch before summarising.
_LIVE_FETCH_TOP_N = 5


class SearchRequest(BaseModel):
    query:         str
    top_k:         int           = Field(default=10, ge=1, le=50)
    domain_filter: Optional[str] = None   # restrict to one domain
    summarize:     bool          = False  # LLM summary of top results


class SearchResult(BaseModel):
    url:       str
    title:     str
    domain:    str
    snippet:   str
    score:     float
    in_vector: bool
    in_bm25:   bool
    image_url: Optional[str] = None   # og:image / twitter:image from live fetch


class SearchResponse(BaseModel):
    query:    str
    results:  List[SearchResult]
    total:    int
    summary:  Optional[str]  = None
    stats:    Optional[dict] = None


@router.post("", response_model=SearchResponse)
async def search(
    req:     SearchRequest,
    session: AsyncSession = Depends(get_session),
):
    if not req.query.strip():
        raise HTTPException(400, "Query cannot be empty")

    # ── 1. BM25 search against our PostgreSQL index ──────────────────────────
    engine = SearchEngine(session)
    raw    = await engine.search(
        query=req.query,
        top_k=req.top_k,
        domain_filter=req.domain_filter,
    )

    # ── 2. Live-fetch the top N results for fresh content + thumbnail ─────────
    fetcher = ContentFetcher()
    cleaner = ContentCleaner()
    parser  = ContentParser()

    async def _live_fetch(result: dict) -> dict:
        """
        Download the page HTML, then in a single pass:
          - parser.parse()  → extracts content text AND og:image from raw HTML
          - cleaner.clean() → strips boilerplate from the text
          - inject snippet, live_content, and image_url back into result
        The image must be read from raw HTML before the parser hands the body
        text to readability (which discards <head>), so parsing always precedes
        cleaning.
        """
        try:
            html = await fetcher.fetch(result["url"])
            if html:
                # parse() reads raw HTML — grabs og:image from <head> here,
                # then extracts body text via readability / BS4.
                parsed    = parser.parse(html, result["url"])
                content   = cleaner.clean(parsed.get("content", ""))
                image_url = parsed.get("image", "")

                if content:
                    result["snippet"]      = content[:1_500]
                    result["live_content"] = content

                # Always store image_url (may be empty string if none found)
                result["image_url"] = image_url or None

        except Exception as e:
            logger.warning(f"Live-fetch failed for {result['url']}: {e}")
        return result

    top_results  = raw[:_LIVE_FETCH_TOP_N]
    rest_results = raw[_LIVE_FETCH_TOP_N:]

    # Run live-fetches concurrently
    top_results = list(
        await asyncio.gather(*[_live_fetch(r) for r in top_results])
    )
    enriched = top_results + rest_results

    # ── 3. Build response objects ─────────────────────────────────────────────
    results = [
        SearchResult(
            url=r["url"],
            title=r.get("title") or _title_from_url(r["url"]),
            domain=r.get("domain", ""),
            snippet=r.get("snippet", ""),
            score=round(r.get("score", 0.0), 6),
            in_vector=r.get("in_vector", False),
            in_bm25=r.get("in_bm25", False),
            image_url=r.get("image_url"),   # None for non-live-fetched results
        )
        for r in enriched
    ]

    # ── 4. Summarise using the live-fetched content ───────────────────────────
    summary = None
    if req.summarize and results:
        live_sources = []
        for r in enriched[:_LIVE_FETCH_TOP_N]:
            live_content = r.get("live_content") or r.get("snippet", "")
            live_sources.append(
                _SummarySource(
                    url=r["url"],
                    title=r.get("title") or _title_from_url(r["url"]),
                    snippet=live_content[:3_000],
                )
            )

        summarizer = Summarizer()
        summary    = await summarizer.summarize_results(req.query, live_sources)

    return SearchResponse(
        query=req.query,
        results=results,
        total=len(results),
        summary=summary,
    )


@router.get("/stats")
async def search_stats(session: AsyncSession = Depends(get_session)):
    """Index health — how many pages are indexed."""
    engine = SearchEngine(session)
    return await engine.index_stats()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _title_from_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        p    = urlparse(url)
        path = p.path.rstrip("/").split("/")[-1]
        return path.replace("-", " ").replace("_", " ").title() or p.netloc
    except Exception:
        return url


class _SummarySource:
    """
    Lightweight stand-in passed to Summarizer so it receives live text.
    Matches the attribute interface Summarizer.summarize_results() expects
    (.title, .url, .snippet).
    """
    def __init__(self, url: str, title: str, snippet: str):
        self.url     = url
        self.title   = title
        self.snippet = snippet
