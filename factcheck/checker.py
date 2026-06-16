"""
Fact Check Module — POST /fact-check endpoint logic
Scores a claim against web evidence
"""

from typing import Dict, List, Optional
from search.aggregator import SearchAggregator
from extractor.fetcher import ContentFetcher
from extractor.cleaner import ContentCleaner
from llm.verifier import FactVerifier
import logging

logger = logging.getLogger(__name__)


class FactChecker:
    def __init__(self):
        self.aggregator = SearchAggregator()
        self.fetcher = ContentFetcher()
        self.cleaner = ContentCleaner(max_chars=3000)
        self.verifier = FactVerifier()

    async def check(self, claim: str) -> Dict:
        """
        1. Search for sources related to the claim
        2. Fetch + clean content
        3. Ask LLM to verify claim against sources

        Returns:
        {
          "claim": str,
          "confidence": float,   # 0.0 - 1.0
          "verified": bool,
          "evidence": [...],
          "sources": [...]
        }
        """
        # Find relevant sources
        results = await self.aggregator.search(claim, num_results=8)

        sources = []
        for r in results:
            content = await self.fetcher.fetch(r["url"])
            if content:
                r["content"] = self.cleaner.clean(content)
            sources.append(r)

        # Verify
        claims = await self.verifier.verify_sources(claim, sources)

        if claims:
            top = claims[0]
            return {
                "claim": claim,
                "confidence": top.get("confidence", 0.5),
                "verified": top.get("verified", False),
                "evidence": top.get("notes", ""),
                "sources": [
                    {"title": s.get("title", ""), "url": s.get("url", "")}
                    for s in sources[:5]
                ],
            }

        return {
            "claim": claim,
            "confidence": 0.0,
            "verified": False,
            "evidence": "Could not gather sufficient evidence.",
            "sources": [],
        }
