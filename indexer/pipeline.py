"""
Indexer Pipeline — crawl a URL and index every page into PostgreSQL.
Full-text search via tsvector trigger; no vector DB required.

Called by the Celery worker and also directly from the crawl API.
"""

import logging
from typing import Optional

from crawler.spider      import Spider
from extractor.parser    import ContentParser
from extractor.cleaner   import ContentCleaner
from database.models     import SessionLocal
from database.repository import PageRepository
from utils.urls          import domain, normalize

logger = logging.getLogger(__name__)

# Maximum characters stored in PostgreSQL as the page description.
# The full content is NOT stored; it is fetched live at query time instead.
_DESCRIPTION_MAX_CHARS = 500


class IndexPipeline:
    """
    Crawl-and-index pipeline for a single seed URL.

    For each page crawled:
      fetch → parse → clean → truncate → save to PG (trigger updates FTS)

    Full content is intentionally NOT stored. A 500-character description
    is saved for display purposes; fresh content is fetched live at search
    time by the API layer.
    """

    def __init__(
        self,
        max_depth:   int = 3,
        max_pages:   int = 200,
        concurrency: int = 5,
    ):
        self.max_depth   = max_depth
        self.max_pages   = max_pages
        self.concurrency = concurrency
        self.parser      = ContentParser()
        self.cleaner     = ContentCleaner()

    async def run(self, start_url: str, job_id: Optional[str] = None) -> dict:
        """
        Crawl start_url and index everything found.
        Returns a summary dict.
        """
        start_url    = normalize(start_url)
        start_domain = domain(start_url)
        indexed      = 0
        failed       = 0
        skipped      = 0

        logger.info(
            f"[IndexPipeline] Starting: {start_url} "
            f"depth={self.max_depth} max={self.max_pages}"
        )

        spider = Spider(
            max_depth=self.max_depth,
            max_pages=self.max_pages,
            concurrency=self.concurrency,
        )

        async for update in spider.crawl(start_url):
            url  = update.get("last_url", "")
            html = update.get("html")

            if not html or not url:
                skipped += 1
                continue

            try:
                parsed  = self.parser.parse(html, url)
                content = self.cleaner.clean(parsed.get("content", ""))

                if not content or len(content.split()) < 30:
                    skipped += 1
                    continue

                title      = parsed.get("title", "")
                word_count = len(content.split())

                # Truncate to a brief description — we do NOT store full content.
                description = content[:_DESCRIPTION_MAX_CHARS]

                # Save to PostgreSQL; the DB trigger updates search_vector automatically.
                async with SessionLocal() as session:
                    repo = PageRepository(session)
                    await repo.upsert(
                        url=url,
                        domain=start_domain,
                        title=title,
                        content=description,
                        word_count=word_count,
                    )

                indexed += 1

                if job_id:
                    logger.debug(f"[{job_id}] Indexed: {url}")

            except Exception as e:
                logger.warning(f"Failed to index {url}: {e}")
                failed += 1

        await self._update_seed(start_url)

        summary = {
            "start_url": start_url,
            "indexed":   indexed,
            "failed":    failed,
            "skipped":   skipped,
        }
        logger.info(f"[IndexPipeline] Done: {summary}")
        return summary

    async def _update_seed(self, url: str):
        """Mark this seed URL as crawled."""
        try:
            from sqlalchemy import text
            async with SessionLocal() as session:
                await session.execute(
                    text("""
                        UPDATE seed_urls
                        SET last_crawled = NOW(), crawl_count = crawl_count + 1
                        WHERE url = :url
                    """),
                    {"url": url},
                )
                await session.commit()
        except Exception:
            pass  # seed_urls entry may not exist for ad-hoc crawls
