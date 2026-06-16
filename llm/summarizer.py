"""
Summarizer — condenses search results into a clear answer
"""

from typing import List
from llm.router import OpenRouterClient
from config import settings

SYSTEM = """You are a search result summarizer. Given a query and search results,
produce a clear, factual summary that directly answers the query.
Be concise (2-4 paragraphs). Cite sources inline as [1], [2] etc."""


class Summarizer:
    def __init__(self):
        self.client = OpenRouterClient(model=settings.fast_model)

    async def summarize_results(self, query: str, results: list) -> str:
        sources_text = "\n\n".join(
            f"[{i+1}] {r.title}\nURL: {r.url}\n{r.snippet or ''}"
            for i, r in enumerate(results[:8])
        )

        prompt = f"Query: {query}\n\nSources:\n{sources_text}"

        return await self.client.complete(
            messages=[{"role": "user", "content": prompt}],
            system=SYSTEM,
            temperature=0.3,
            max_tokens=1024,
        )
