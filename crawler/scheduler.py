"""
Crawl Scheduler — manages crawl job queue (Redis-backed in production)
"""

import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class CrawlTask:
    url: str
    depth: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    retries: int = 0


class CrawlScheduler:
    """
    In-memory scheduler. In production, back with Redis sorted sets.
    Priority: shallow pages first (BFS).
    """

    def __init__(self, max_retries: int = 2, delay_ms: int = 500):
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._seen: set = set()
        self.max_retries = max_retries
        self.delay_ms = delay_ms

    async def enqueue(self, url: str, depth: int = 0):
        if url not in self._seen:
            self._seen.add(url)
            task = CrawlTask(url=url, depth=depth)
            # Priority = depth (lower depth = higher priority)
            await self._queue.put((depth, task))

    async def dequeue(self) -> Optional[CrawlTask]:
        try:
            _, task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            await asyncio.sleep(self.delay_ms / 1000)  # Polite delay
            return task
        except asyncio.TimeoutError:
            return None

    def size(self) -> int:
        return self._queue.qsize()

    def is_empty(self) -> bool:
        return self._queue.empty()
