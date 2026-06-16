"""
Tests for GET /health  (app-level smoke tests)
"""

import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data


@pytest.mark.asyncio
async def test_health_version_format(client):
    resp = await client.get("/health")
    version = resp.json()["version"]
    parts = version.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


@pytest.mark.asyncio
async def test_openapi_schema_accessible(client):
    resp = await client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "paths" in schema
    # All five route groups should be present
    paths = schema["paths"]
    assert any("/search" in p for p in paths)
    assert any("/research" in p for p in paths)
    assert any("/crawl" in p for p in paths)
    assert any("/fact-check" in p for p in paths)
