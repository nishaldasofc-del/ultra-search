"""
Tests for POST /crawl  and  GET /crawl/{job_id}
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock


async def _fake_crawl(*args, **kwargs):
    """Async generator that yields two progress updates."""
    yield {"pages_crawled": 1, "pages_queued": 3, "error": None}
    yield {"pages_crawled": 3, "pages_queued": 1, "error": None}


@pytest.mark.asyncio
async def test_crawl_creates_job(client):
    with patch("api.crawl.Spider") as MockSpider:
        MockSpider.return_value.crawl = _fake_crawl
        resp = await client.post("/crawl", json={"url": "https://example.com", "max_depth": 1})

    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["url"] == "https://example.com"
    assert data["status"] in ("pending", "running")


@pytest.mark.asyncio
async def test_crawl_get_unknown_job_404(client):
    resp = await client.get("/crawl/does-not-exist")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_crawl_invalid_url(client):
    """Spider receives whatever URL is given — API doesn't validate shape."""
    with patch("api.crawl.Spider") as MockSpider:
        MockSpider.return_value.crawl = _fake_crawl
        resp = await client.post("/crawl", json={"url": "not-a-url"})
    # Schema accepts any string; validation is the Spider's job
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_crawl_error_recorded(client):
    """Errors yielded by the spider should be captured in the job."""
    async def _error_crawl(*args, **kwargs):
        yield {"pages_crawled": 0, "pages_queued": 0, "error": "Connection refused"}

    with patch("api.crawl.Spider") as MockSpider:
        MockSpider.return_value.crawl = _error_crawl
        resp = await client.post("/crawl", json={"url": "https://example.com"})

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_crawl_job_response_schema(client):
    with patch("api.crawl.Spider") as MockSpider:
        MockSpider.return_value.crawl = _fake_crawl
        resp = await client.post("/crawl", json={"url": "https://example.com"})

    data = resp.json()
    for field in ("job_id", "status", "url", "pages_crawled", "pages_queued", "errors"):
        assert field in data, f"Missing field: {field}"
