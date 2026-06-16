"""
Tests for POST /fact-check
"""

import pytest
from unittest.mock import AsyncMock, patch


def _mock_result(verified=True, confidence=0.85):
    return {
        "claim":      "The Earth orbits the Sun.",
        "confidence": confidence,
        "verified":   verified,
        "evidence":   "Multiple sources confirm heliocentric orbit.",
        "sources":    [{"url": "https://nasa.gov", "title": "NASA", "snippet": "..."}],
    }


@pytest.mark.asyncio
async def test_factcheck_verified_claim(client):
    with patch("api.factcheck.FactChecker") as MockChecker:
        MockChecker.return_value.check = AsyncMock(return_value=_mock_result(verified=True))
        resp = await client.post("/fact-check", json={"claim": "The Earth orbits the Sun."})

    assert resp.status_code == 200
    data = resp.json()
    assert data["verified"] is True
    assert 0.0 <= data["confidence"] <= 1.0
    assert isinstance(data["sources"], list)
    assert data["evidence"]


@pytest.mark.asyncio
async def test_factcheck_false_claim(client):
    with patch("api.factcheck.FactChecker") as MockChecker:
        MockChecker.return_value.check = AsyncMock(return_value=_mock_result(verified=False, confidence=0.1))
        resp = await client.post("/fact-check", json={"claim": "The Moon is made of cheese."})

    assert resp.status_code == 200
    assert resp.json()["verified"] is False


@pytest.mark.asyncio
async def test_factcheck_empty_claim_400(client):
    resp = await client.post("/fact-check", json={"claim": "   "})
    assert resp.status_code == 400
    assert "empty" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_factcheck_missing_claim_422(client):
    resp = await client.post("/fact-check", json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_factcheck_response_schema(client):
    with patch("api.factcheck.FactChecker") as MockChecker:
        MockChecker.return_value.check = AsyncMock(return_value=_mock_result())
        resp = await client.post("/fact-check", json={"claim": "Python was created in 1991."})

    data = resp.json()
    for field in ("claim", "confidence", "verified", "evidence", "sources"):
        assert field in data, f"Missing response field: {field}"
