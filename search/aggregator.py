import logging
from typing import List, Dict
from database.models import SessionLocal
from search.engine import SearchEngine

logger = logging.getLogger(__name__)

class SearchAggregator:
    """
    Acts as the local search provider for the Research and Fact-Check agents.
    Queries our own PostgreSQL database instead of external APIs.
    """
    async def search(self, query: str, num_results: int = 10) -> List[Dict]:
        async with SessionLocal() as session:
            engine = SearchEngine(session)
            results = await engine.search(query=query, top_k=num_results)
            return results
