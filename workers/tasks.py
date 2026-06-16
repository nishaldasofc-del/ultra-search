"""
Celery Tasks — async-friendly wrappers for background work.
All heavy tasks run the indexer pipeline (PostgreSQL only; no Qdrant).
"""

import asyncio
import logging
from celery import Celery
from config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "ultrasearch",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_routes={
        "workers.tasks.index_url":         {"queue": "crawl"},
        "workers.tasks.index_seed_url":    {"queue": "crawl"},
        "workers.tasks.recrawl_due_seeds": {"queue": "crawl"},
        "workers.tasks.purge_old_reports": {"queue": "default"},
        "workers.tasks.evict_sessions":    {"queue": "default"},
    },
)


def _run(coro):
    """Run an async coroutine from a sync Celery task."""
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Core indexing task ────────────────────────────────────────────────────────

@celery_app.task(
    name="workers.tasks.index_url",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
)
def index_url(self, url: str, max_depth: int = 3, max_pages: int = 200):
    """
    Crawl and index a URL into PostgreSQL (BM25 / FTS).
    Called by the crawl API for ad-hoc indexing jobs.
    """
    logger.info(f"[index_url] Starting: {url}")
    try:
        from indexer.pipeline import IndexPipeline
        pipeline = IndexPipeline(max_depth=max_depth, max_pages=max_pages)
        summary  = _run(pipeline.run(url))
        logger.info(f"[index_url] Done: {summary}")
        return summary
    except Exception as e:
        logger.exception(f"[index_url] Failed for {url}: {e}")
        raise self.retry(exc=e)


@celery_app.task(name="workers.tasks.index_seed_url")
def index_seed_url(url: str, max_depth: int = 3, max_pages: int = 200):
    """Same as index_url but specifically for scheduled seed re-crawls."""
    from indexer.pipeline import IndexPipeline
    pipeline = IndexPipeline(max_depth=max_depth, max_pages=max_pages)
    return _run(pipeline.run(url))


# ── Periodic tasks (invoked by Celery Beat) ───────────────────────────────────

@celery_app.task(name="workers.tasks.recrawl_due_seeds")
def recrawl_due_seeds():
    """
    Check seed_urls table for domains due for re-crawl.
    Runs hourly via beat. Each due seed gets its own index_seed_url task.
    """
    from indexer.scheduler import get_seeds_due_for_crawl

    seeds = _run(get_seeds_due_for_crawl())
    logger.info(f"[beat] {len(seeds)} seeds due for re-crawl")

    for seed in seeds:
        index_seed_url.apply_async(
            args=[seed["url"]],
            kwargs={"max_depth": seed["max_depth"], "max_pages": seed["max_pages"]},
            queue="crawl",
        )

    return {"triggered": len(seeds)}


@celery_app.task(name="workers.tasks.purge_old_reports")
def purge_old_reports(days: int = 30):
    """Delete research reports older than `days` days."""
    from datetime import datetime, timedelta
    from database.models import SessionLocal
    from sqlalchemy import text

    async def _run_purge():
        cutoff = datetime.utcnow() - timedelta(days=days)
        async with SessionLocal() as session:
            await session.execute(
                text("DELETE FROM research_reports WHERE created_at < :cutoff"),
                {"cutoff": cutoff},
            )
            await session.commit()

    _run(_run_purge())
    return {"purged": True, "older_than_days": days}


@celery_app.task(name="workers.tasks.evict_sessions")
def evict_sessions():
    """Evict expired in-memory sessions."""
    from memory.store import memory
    if hasattr(memory, "evict_expired"):
        memory.evict_expired()
    return {"evicted": True}
