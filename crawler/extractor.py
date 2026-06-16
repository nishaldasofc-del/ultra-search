"""
Crawler Extractor — extracts and indexes page content during crawl
Ties together parser + cleaner + vector embedding for crawled pages
"""

from typing import Optional, Dict
from extractor.parser import ContentParser
from extractor.cleaner import ContentCleaner
import logging

logger = logging.getLogger(__name__)


class CrawlerExtractor:
    """
    Called by the spider after fetching each page.
    Parses HTML → cleans content → returns structured record for indexing.
    """

    def __init__(self):
        self.parser = ContentParser()
        self.cleaner = ContentCleaner(max_chars=10_000)

    def extract(self, html: str, url: str) -> Optional[Dict]:
        try:
            parsed = self.parser.parse(html, url=url)
            body = self.cleaner.clean(parsed.get("body", ""))
            if not body or len(body) < 100:
                logger.debug(f"Skipping low-content page: {url}")
                return None

            return {
                "url": url,
                "title": parsed.get("title", ""),
                "description": parsed.get("description", ""),
                "content": body,
                "word_count": parsed.get("word_count", 0),
            }
        except Exception as e:
            logger.warning(f"Extraction failed for {url}: {e}")
            return None
