"""
Robots.txt cache — fetches and respects robots.txt per domain.
Caches parsed rules in memory for the lifetime of the crawler process.
"""

import httpx
import asyncio
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
from typing import Dict
from config import settings
import logging

logger = logging.getLogger(__name__)


class RobotsCache:
    def __init__(self):
        self._cache: Dict[str, RobotFileParser] = {}
        self._lock  = asyncio.Lock()

    async def is_allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        domain = parsed.netloc
        robots_url = f"{parsed.scheme}://{domain}/robots.txt"

        async with self._lock:
            if domain not in self._cache:
                self._cache[domain] = await self._fetch(robots_url)

        return self._cache[domain].can_fetch(settings.crawler_user_agent, url)

    async def _fetch(self, robots_url: str) -> RobotFileParser:
        rp = RobotFileParser()
        try:
            async with httpx.AsyncClient(timeout=8) as client:
                resp = await client.get(robots_url)
            if resp.status_code == 200:
                rp.parse(resp.text.splitlines())
            else:
                # No robots.txt = allow everything
                rp.allow_all = True
        except Exception:
            rp.allow_all = True
        return rp
