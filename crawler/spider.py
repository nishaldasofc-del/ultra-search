"""
Spider — async BFS web crawler with sitemap support.
Yields progress updates including the raw HTML for the indexer.
"""

import asyncio
import httpx
from urllib.parse import urljoin, urlparse
from typing import AsyncGenerator, Dict, Set, List, Optional
from bs4 import BeautifulSoup
from crawler.robots import RobotsCache
from config import settings
import logging

logger = logging.getLogger(__name__)

SKIP_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
    ".mp4", ".mp3", ".zip", ".tar", ".gz", ".exe", ".dmg",
    ".css", ".js", ".ico", ".woff", ".woff2", ".ttf",
}


class Spider:
    def __init__(
        self,
        max_depth:       int  = 3,
        max_pages:       int  = 200,
        follow_external: bool = False,
        respect_robots:  bool = True,
        concurrency:     int  = 5,
        delay_ms:        int  = 300,
    ):
        self.max_depth       = max_depth
        self.max_pages       = max_pages
        self.follow_external = follow_external
        self.respect_robots  = respect_robots
        self.concurrency     = concurrency
        self.delay_ms        = delay_ms
        self.robots          = RobotsCache()

    async def crawl(self, start_url: str) -> AsyncGenerator[Dict, None]:
        """
        Async BFS crawl. Yields dict per page:
          { pages_crawled, pages_queued, last_url, html, error }
        """
        start_domain = urlparse(start_url).netloc
        visited:  Set[str]    = set()
        queue:    List[tuple] = [(start_url, 0)]   # (url, depth)
        pages_crawled = 0

        # Discover sitemap links first to seed the queue
        sitemap_urls = await self._parse_sitemap(start_url)
        for surl in sitemap_urls[:500]:
            if surl not in visited:
                queue.append((surl, 1))
                visited.add(surl)

        semaphore = asyncio.Semaphore(self.concurrency)

        async def fetch_page(url: str, depth: int):
            nonlocal pages_crawled
            async with semaphore:
                # Politeness delay
                if self.delay_ms:
                    await asyncio.sleep(self.delay_ms / 1000)
                try:
                    # Skip binary/media URLs
                    path = urlparse(url).path.lower()
                    if any(path.endswith(ext) for ext in SKIP_EXTENSIONS):
                        return url, depth, [], None, None

                    if self.respect_robots and not await self.robots.is_allowed(url):
                        logger.debug(f"robots.txt disallows: {url}")
                        return url, depth, [], None, None

                    async with httpx.AsyncClient(
                        timeout=15,
                        follow_redirects=True,
                        headers={"User-Agent": settings.crawler_user_agent},
                    ) as client:
                        resp = await client.get(url)

                    if resp.status_code != 200:
                        return url, depth, [], None, f"HTTP {resp.status_code}"

                    content_type = resp.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        return url, depth, [], None, None

                    html  = resp.text
                    links = self._extract_links(html, url, start_domain, depth)
                    pages_crawled += 1
                    return url, depth, links, html, None

                except Exception as e:
                    logger.warning(f"Crawl error {url}: {e}")
                    return url, depth, [], None, str(e)

        while queue and pages_crawled < self.max_pages:
            batch = queue[: self.concurrency]
            queue = queue[self.concurrency :]

            tasks   = [fetch_page(url, depth) for url, depth in batch]
            results = await asyncio.gather(*tasks)

            for url, depth, links, html, error in results:
                visited.add(url)

                if links and depth < self.max_depth:
                    for link in links:
                        if link not in visited:
                            queue.append((link, depth + 1))
                            visited.add(link)

                yield {
                    "pages_crawled": pages_crawled,
                    "pages_queued":  len(queue),
                    "last_url":      url,
                    "html":          html,
                    "error":         error,
                }

    def _extract_links(
        self, html: str, base_url: str, base_domain: str, current_depth: int
    ) -> List[str]:
        if current_depth >= self.max_depth:
            return []

        soup  = BeautifulSoup(html, "html.parser")
        links = []

        for tag in soup.find_all("a", href=True):
            href     = tag["href"].strip()
            full_url = urljoin(base_url, href).split("#")[0]
            parsed   = urlparse(full_url)

            if parsed.scheme not in ("http", "https"):
                continue
            if not self.follow_external and parsed.netloc != base_domain:
                continue

            links.append(full_url)

        return list(set(links))

    async def _parse_sitemap(self, start_url: str) -> List[str]:
        """Try to fetch sitemap.xml and extract URLs."""
        parsed = urlparse(start_url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        urls = []
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(sitemap_url)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "xml")
                for loc in soup.find_all("loc"):
                    urls.append(loc.text.strip())
                logger.info(f"Sitemap found: {len(urls)} URLs from {sitemap_url}")
        except Exception:
            pass
        return urls
