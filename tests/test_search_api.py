"""
Tests for POST /search
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


# ── helpers ───────────────────────────────────────────────────────────────────
def _make_search_payload(query="Python programming", **overrides):
    return {"query": query, "num_results": 5, "sources": ["brave"], **overrides}


# ── happy path ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_search_returns_results(client, mock_search_results, mock_llm_summary):
    with (
        patch("api.search.SearchAggregator") as MockAgg,
        patch("api.search.ContentFetcher")   as MockFetch,
        patch("api.search.ContentCleaner")   as MockClean,
        patch("api.search.Summarizer")       as MockSumm,
    ):
        MockAgg.return_value.search       = AsyncMock(return_value=mock_search_results)
        MockFetch.return_value.fetch      = AsyncMock(return_value="<html>content</html>")
        MockClean.return_value.clean      = MagicMock(return_value="cleaned content")
        MockSumm.return_value.summarize_results = AsyncMock(return_value=mock_llm_summary)

        resp = await client.post("/search", json=_make_search_payload())

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "Python programming"
    assert len(data["results"]) == 2
    assert data["summary"] == mock_llm_summary
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_search_no_content_extraction(client, mock_search_results):
    with patch("api.search.SearchAggregator") as MockAgg:
        MockAgg.return_value.search = AsyncMock(return_value=mock_search_results)

        resp = await client.post(
            "/search",
            json=_make_search_payload(extract_content=False, summarize=False),
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["summary"] is None
    assert all(r["content"] is None for r in data["results"])


# ── validation ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_search_empty_query_returns_400(client):
    resp = await client.post("/search", json={"query": "  ", "sources": ["brave"]})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_search_missing_query_returns_422(client):
    resp = await client.post("/search", json={"num_results": 5})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_search_result_structure(client, mock_search_results):
    with (
        patch("api.search.SearchAggregator") as MockAgg,
        patch("api.search.ContentFetcher")   as MockFetch,
        patch("api.search.ContentCleaner")   as MockClean,
        patch("api.search.Summarizer")       as MockSumm,
    ):
        MockAgg.return_value.search             = AsyncMock(return_value=mock_search_results)
        MockFetch.return_value.fetch            = AsyncMock(return_value="html")
        MockClean.return_value.clean            = MagicMock(return_value="text")
        MockSumm.return_value.summarize_results = AsyncMock(return_value="summary")

        resp = await client.post("/search", json=_make_search_payload())

    result = resp.json()["results"][0]
    for field in ("title", "url", "snippet", "score"):
        assert field in result, f"Missing field: {field}"
