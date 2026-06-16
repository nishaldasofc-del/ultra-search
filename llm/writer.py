"""
Report Writer Agent — compiles final research report
"""

from typing import List, Dict, Optional
from llm.router import OpenRouterClient
from llm.planner import ResearchPlan
from config import settings
import logging

logger = logging.getLogger(__name__)

SYSTEM = """You are an expert research writer. Given a research plan, sources, and verified claims,
write a comprehensive, well-structured research report.

Return JSON:
{
  "title": "Report title",
  "executive_summary": "2-3 sentence summary",
  "sections": [
    {
      "heading": "Section heading",
      "content": "Section content with inline citations [1], [2]...",
      "key_points": ["point1", "point2"]
    }
  ],
  "conclusion": "Concluding paragraph",
  "sources": [
    {"index": 0, "title": "...", "url": "..."}
  ],
  "confidence_score": 0.92,
  "metadata": {
    "sources_consulted": 10,
    "claims_verified": 5
  }
}"""


class ReportWriter:
    def __init__(self):
        self.client = OpenRouterClient(model=settings.deep_model)

    async def write(
        self,
        query: str,
        plan: ResearchPlan,
        sources: List[Dict],
        verified_claims: Optional[List[Dict]] = None,
    ) -> Dict:
        source_digest = "\n".join(
            f"[{i}] {s.get('title','')}: {(s.get('content') or s.get('snippet',''))[:600]}"
            for i, s in enumerate(sources[:12])
        )

        claims_text = ""
        if verified_claims:
            claims_text = "\n\nVerified Claims:\n" + "\n".join(
                f"- {c.get('claim','')} (confidence: {c.get('confidence', 0):.0%})"
                for c in verified_claims[:10]
            )

        prompt = (
            f"Query: {query}\n"
            f"Research Goal: {plan.goal}\n"
            f"Key Aspects: {', '.join(plan.key_aspects)}\n\n"
            f"Sources:\n{source_digest}"
            f"{claims_text}"
        )

        try:
            return await self.client.complete_json(
                messages=[{"role": "user", "content": prompt}],
                system=SYSTEM,
                temperature=0.3,
                max_tokens=4096,
            )
        except Exception as e:
            logger.error(f"Report writing failed: {e}")
            return {
                "title": query,
                "executive_summary": "Report generation failed.",
                "sections": [],
                "conclusion": "",
                "sources": [],
                "error": str(e),
            }
