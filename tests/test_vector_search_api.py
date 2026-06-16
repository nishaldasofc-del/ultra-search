"""
Tests for POST /vector-search
"""

import pytest
from unittest.mock import AsyncMock, patch


def _mock_vector_results():
    return [
        {"url": "https://python.org", "title": "Python", "text": "Python is a language.",
         "_score": 0.92, "chunk_index": 0},
        {"url": "https://docs.python.org", "title": "Docs", "text": "Documentation.",
         "_score": 0.78, "chunk_index": 1},
    ]


@pytest.mark.asyncio
async def test_vector_search_returns_results(client):
    with patch("api.vector_search.SemanticSearch") as MockSearch:
        MockSearch.return_value.search = AsyncMock(return_value=_mock_vector_results())
        resp = await client.post("/vector-search", json={"query": "Python language"})

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "Python language"
    assert len(data["results"]) == 2
    assert data["total"] == 2


@pytest.mark.asyncio
async def test_vector_search_result_schema(client):
    with patch("api.vector_search.SemanticSearch") as MockSearch:
        MockSearch.return_value.search = AsyncMock(return_value=_mock_vector_results())
        resp = await client.post("/vector-search", json={"query": "test"})

    r = resp.json()["results"][0]
    for field in ("url", "title", "text", "score", "chunk_index"):
        assert field in r, f"Missing field: {field}"
    assert 0.0 <= r["score"] <= 1.0


@pytest.mark.asyncio
async def test_vector_search_empty_query_400(client):
    resp = await client.post("/vector-search", json={"query": ""})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_vector_search_no_results(client):
    with patch("api.vector_search.SemanticSearch") as MockSearch:
        MockSearch.return_value.search = AsyncMock(return_value=[])
        resp = await client.post("/vector-search", json={"query": "xyzzy123"})

    assert resp.status_code == 200
    assert resp.json()["total"] == 0
    assert resp.json()["results"] == []


@pytest.mark.asyncio
async def test_vector_search_top_k_param(client):
    results = _mock_vector_results()
    with patch("api.vector_search.SemanticSearch") as MockSearch:
        instance = MockSearch.return_value
        instance.search = AsyncMock(return_value=results)
        await client.post("/vector-search", json={"query": "test", "top_k": 3})

    instance.search.assert_called_once_with("test", top_k=3, min_score=0.5)
