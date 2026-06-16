"""
Content Fetcher — downloads pages with retry logic and browser-like headers
"""

import httpx
import asyncio
from typing import Optional
import logging

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

SKIP_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".zip", ".png", ".jpg", ".mp4", ".mp3"}


class ContentFetcher:
    def __init__(self, timeout: int = 15, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries

    def _should_skip(self, url: str) -> bool:
        lower = url.lower().split("?")[0]
        return any(lower.endswith(ext) for ext in SKIP_EXTENSIONS)

    async def fetch(self, url: str) -> Optional[str]:
        if self._should_skip(url):
            logger.debug(f"Skipping non-HTML URL: {url}")
            return None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    headers=HEADERS,
                    timeout=self.timeout,
                    follow_redirects=True,
                    max_redirects=5,
                ) as client:
                    resp = await client.get(url)
                    content_type = resp.headers.get("content-type", "")
                    if "text/html" not in content_type and "text/plain" not in content_type:
                        logger.debug(f"Skipping non-HTML content: {url} ({content_type})")
                        return None
                    return resp.text
            except httpx.TimeoutException:
                logger.warning(f"Timeout fetching {url} (attempt {attempt + 1})")
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP {e.response.status_code} for {url}")
                return None
            except Exception as e:
                logger.warning(f"Error fetching {url}: {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(1)

        return None
