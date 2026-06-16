"""
Crawl Queue — PostgreSQL-backed persistent queue for production crawls
Falls back to in-memory list for dev/testing
"""

import asyncio
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class QueueItem:
    url: str
    depth: int = 0
    priority: float = 0.0
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()


class InMemoryQueue:
    """Simple in-memory priority queue (depth = priority, lower is better)."""

    def __init__(self):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._seen: set = set()

    async def push(self, url: str, depth: int = 0, priority: float = 0.0):
        if url not in self._seen:
            self._seen.add(url)
            item = QueueItem(url=url, depth=depth, priority=priority)
            await self._queue.put((depth - priority, item))

    async def pop(self) -> Optional[QueueItem]:
        try:
            _, item = await asyncio.wait_for(self._queue.get(), timeout=0.5)
            return item
        except asyncio.TimeoutError:
            return None

    def size(self) -> int:
        return self._queue.qsize()

    def seen(self) -> int:
        return len(self._seen)


class PostgresQueue:
    """
    PostgreSQL-backed persistent queue.
    Uses advisory locks so multiple workers don't process the same URL.
    """

    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def push(self, url: str, depth: int = 0, priority: float = 0.0):
        from sqlalchemy import text
        async with self.session_factory() as session:
            await session.execute(
                text("""
                    INSERT INTO crawl_queue (url, depth, priority)
                    VALUES (:url, :depth, :priority)
                    ON CONFLICT (url) DO NOTHING
                """),
                {"url": url, "depth": depth, "priority": priority},
            )
            await session.commit()

    async def pop(self) -> Optional[QueueItem]:
        from sqlalchemy import text
        async with self.session_factory() as session:
            result = await session.execute(
                text("""
                    DELETE FROM crawl_queue
                    WHERE id = (
                        SELECT id FROM crawl_queue
                        WHERE NOT locked
                        ORDER BY depth ASC, priority DESC
                        LIMIT 1
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING url, depth, priority
                """)
            )
            row = result.fetchone()
            await session.commit()
            if row:
                return QueueItem(url=row.url, depth=row.depth, priority=row.priority)
            return None

    async def size(self) -> int:
        from sqlalchemy import text
        async with self.session_factory() as session:
            result = await session.execute(text("SELECT COUNT(*) FROM crawl_queue"))
            return result.scalar()
