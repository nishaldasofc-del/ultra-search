"""
Fact Verifier Agent
Cross-checks claims across multiple sources and scores confidence
"""

from typing import List, Dict
from llm.router import OpenRouterClient
from config import settings
import logging

logger = logging.getLogger(__name__)

SYSTEM = """You are a fact-checking expert. Given a query and multiple sources,
extract key claims and verify them by cross-referencing sources.

Return JSON:
{
  "claims": [
    {
      "claim": "The claim text",
      "confidence": 0.95,
      "verified": true,
      "supporting_sources": [0, 2],
      "contradicting_sources": [],
      "notes": "Optional notes"
    }
  ],
  "overall_confidence": 0.87
}"""


class FactVerifier:
    def __init__(self):
        self.client = OpenRouterClient(model=settings.deep_model)

    async def verify_sources(self, query: str, sources: List[Dict]) -> List[Dict]:
        if not sources:
            return []

        # Build source digest (avoid huge prompts)
        source_text = "\n\n".join(
            f"[{i}] {s.get('title', '')}: {(s.get('content') or s.get('snippet', ''))[:500]}"
            for i, s in enumerate(sources[:10])
        )

        prompt = f"Query: {query}\n\nSources:\n{source_text}"

        try:
            data = await self.client.complete_json(
                messages=[{"role": "user", "content": prompt}],
                system=SYSTEM,
                temperature=0.1,
                max_tokens=2048,
            )
            return data.get("claims", [])
        except Exception as e:
            logger.warning(f"Fact verification failed: {e}")
            return []
