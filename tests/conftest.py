"""
Shared pytest fixtures for Ultra Search test suite.
"""

import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

# ── event loop ────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the entire test session."""
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ── app ───────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def app():
    """Import app with mocked settings."""
    with patch.dict("os.environ", {
        "OPENROUTER_API_KEY": "test-key-000",
        "BRAVE_API_KEY":      "test-brave",
        "POSTGRES_URL":       "postgresql://postgres:postgres@localhost:5432/test_ultrasearch",
        "REDIS_URL":          "redis://localhost:6379",
    }):
        from app import app as _app
        return _app


@pytest_asyncio.fixture
async def client(app):
    """HTTPX async test client."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac


# ── mocks ─────────────────────────────────────────────────────────────────────
@pytest.fixture
def mock_search_results():
    return [
        {"title": "Python Docs", "url": "https://docs.python.org", "snippet": "Official Python docs", "score": 0.9},
        {"title": "Real Python",  "url": "https://realpython.com",  "snippet": "Python tutorials",    "score": 0.8},
    ]

@pytest.fixture
def mock_llm_summary():
    return "Python is a high-level, interpreted programming language."

@pytest.fixture
def mock_research_plan():
    plan = MagicMock()
    plan.sub_queries = ["What is Python?", "Python history", "Python use cases"]
    plan.outline    = ["Introduction", "History", "Use Cases"]
    return plan

@pytest.fixture
def mock_report():
    return {
        "title":    "Python: A Comprehensive Overview",
        "sections": [{"heading": "Introduction", "content": "Python is..."}],
        "sources":  ["https://python.org"],
        "claims":   [],
    }
