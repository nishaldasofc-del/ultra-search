"""
Research Planner Agent
Breaks a complex query into a structured research plan with sub-queries
"""

from dataclasses import dataclass, field
from typing import List
from llm.router import OpenRouterClient
from config import settings
import logging

logger = logging.getLogger(__name__)

SYSTEM = """You are a research planning expert. Given a query, produce a JSON research plan.

Return JSON with this exact shape:
{
  "goal": "One sentence describing the research goal",
  "sub_queries": ["query1", "query2", ...],
  "key_aspects": ["aspect1", "aspect2", ...],
  "suggested_sources": ["source type1", "source type2"]
}

Produce 3-8 sub_queries depending on depth requested."""


@dataclass
class ResearchPlan:
    goal: str
    sub_queries: List[str] = field(default_factory=list)
    key_aspects: List[str] = field(default_factory=list)
    suggested_sources: List[str] = field(default_factory=list)


class ResearchPlanner:
    def __init__(self):
        self.client = OpenRouterClient(model=settings.fast_model)

    async def plan(self, query: str, depth: int = 2) -> ResearchPlan:
        depth_instruction = {
            1: "Use 3 sub-queries (quick overview).",
            2: "Use 5 sub-queries (standard research).",
            3: "Use 8 sub-queries (deep investigation).",
        }.get(depth, "Use 5 sub-queries.")

        data = await self.client.complete_json(
            messages=[{"role": "user", "content": f"Query: {query}\n\nDepth: {depth_instruction}"}],
            system=SYSTEM,
            temperature=0.2,
        )

        return ResearchPlan(
            goal=data.get("goal", query),
            sub_queries=data.get("sub_queries", [query]),
            key_aspects=data.get("key_aspects", []),
            suggested_sources=data.get("suggested_sources", []),
        )
