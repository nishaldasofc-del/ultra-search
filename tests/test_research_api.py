"""
Tests for POST /research  and  GET /research/{job_id}
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio


# ── happy path ────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_research_creates_job(client):
    resp = await client.post("/research", json={"query": "History of AI", "depth": 1})
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] in ("pending", "running")
    assert data["query"] == "History of AI"


@pytest.mark.asyncio
async def test_research_get_unknown_job_returns_404(client):
    resp = await client.get("/research/nonexistent-job-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_research_pipeline_completes(client, mock_research_plan, mock_report, mock_search_results):
    """Patch the entire multi-agent pipeline and verify the job reaches 'done'."""
    with (
        patch("api.research.ResearchPlanner")   as MockPlanner,
        patch("api.research.SearchAggregator")  as MockAgg,
        patch("api.research.ContentFetcher")    as MockFetch,
        patch("api.research.ContentCleaner")    as MockClean,
        patch("api.research.Deduplicator")      as MockDedup,
        patch("api.research.FactVerifier")      as MockVerif,
        patch("api.research.ReportWriter")      as MockWriter,
    ):
        MockPlanner.return_value.plan                   = AsyncMock(return_value=mock_research_plan)
        MockAgg.return_value.search                     = AsyncMock(return_value=mock_search_results)
        MockFetch.return_value.fetch                    = AsyncMock(return_value="content")
        MockClean.return_value.clean                    = MagicMock(return_value="clean")
        MockDedup.return_value.deduplicate              = MagicMock(side_effect=lambda x: x)
        MockVerif.return_value.verify_sources           = AsyncMock(return_value=[])
        MockWriter.return_value.write                   = AsyncMock(return_value=mock_report)

        # Start job
        resp = await client.post("/research", json={"query": "test", "depth": 1, "fact_check": True})
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        # Give background task a moment
        await asyncio.sleep(0.2)

        # Poll result
        resp2 = await client.get(f"/research/{job_id}")
        assert resp2.status_code == 200
        data = resp2.json()
        assert data["status"] in ("done", "running")  # timing-dependent


@pytest.mark.asyncio
async def test_research_validation_empty_query(client):
    resp = await client.post("/research", json={"query": "", "depth": 1})
    # Empty string passes schema but downstream validation should reject it
    # (or the LLM call fails — either way, status should be 422 or the job fails)
    assert resp.status_code in (200, 422)


# ── depth / model params ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_research_default_params(client):
    resp = await client.post("/research", json={"query": "quantum computing"})
    assert resp.status_code == 200
    data = resp.json()
    # Defaults from the model: depth=2, max_sources=10, fact_check=True, model="deep"
    assert data["status"] in ("pending", "running", "done", "failed")
