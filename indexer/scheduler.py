"""
Indexer Scheduler — manages seed URLs and triggers continuous re-indexing.
Runs as a Celery periodic task every hour.

Seeds are stored in the seed_urls table. Add domains you want indexed there.
"""

import logging
from datetime import datetime, timedelta
from sqlalchemy import text

from database.models import SessionLocal

logger = logging.getLogger(__name__)

# How old does a crawl need to be before we re-crawl?
RECRAWL_AFTER_HOURS = 24


async def get_seeds_due_for_crawl() -> list:
    """
    Return seed URLs that haven't been crawled in RECRAWL_AFTER_HOURS.
    """
    cutoff = datetime.utcnow() - timedelta(hours=RECRAWL_AFTER_HOURS)

    async with SessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT url, max_depth, max_pages
                FROM seed_urls
                WHERE active = true
                  AND (last_crawled IS NULL OR last_crawled < :cutoff)
                ORDER BY last_crawled ASC NULLS FIRST
                LIMIT 20
            """),
            {"cutoff": cutoff},
        )
        return [
            {"url": row.url, "max_depth": row.max_depth, "max_pages": row.max_pages}
            for row in result.fetchall()
        ]


async def add_seed(url: str, max_depth: int = 3, max_pages: int = 200):
    """Add a new seed URL to the index queue."""
    from utils.urls import normalize
    url = normalize(url)

    async with SessionLocal() as session:
        await session.execute(
            text("""
                INSERT INTO seed_urls (url, max_depth, max_pages, active, added_at)
                VALUES (:url, :max_depth, :max_pages, true, NOW())
                ON CONFLICT (url) DO UPDATE
                    SET max_depth = :max_depth,
                        max_pages = :max_pages,
                        active    = true
            """),
            {"url": url, "max_depth": max_depth, "max_pages": max_pages},
        )
        await session.commit()
    logger.info(f"Seed added: {url}")


async def remove_seed(url: str):
    """Deactivate a seed URL (doesn't delete, just stops crawling it)."""
    async with SessionLocal() as session:
        await session.execute(
            text("UPDATE seed_urls SET active = false WHERE url = :url"),
            {"url": url},
        )
        await session.commit()
    logger.info(f"Seed deactivated: {url}")


async def list_seeds() -> list:
    """Return all seed URLs and their status."""
    async with SessionLocal() as session:
        result = await session.execute(
            text("""
                SELECT url, max_depth, max_pages, active,
                       last_crawled, crawl_count, added_at
                FROM seed_urls
                ORDER BY added_at DESC
            """)
        )
        return [dict(row._mapping) for row in result.fetchall()]
