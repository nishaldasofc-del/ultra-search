"""
Tests for middleware.rate_limit — InMemoryRateLimiter
"""

import pytest
import asyncio
from middleware.rate_limit import InMemoryRateLimiter, _resolve_limit, ROUTE_LIMITS


class TestInMemoryRateLimiter:
    def setup_method(self):
        self.limiter = InMemoryRateLimiter()

    @pytest.mark.asyncio
    async def test_first_request_allowed(self):
        ok, retry = await self.limiter.is_allowed("ip:path", limit=5, window=60)
        assert ok is True
        assert retry == 0

    @pytest.mark.asyncio
    async def test_within_limit_allowed(self):
        for _ in range(4):
            ok, _ = await self.limiter.is_allowed("ip2:path", limit=5, window=60)
            assert ok

    @pytest.mark.asyncio
    async def test_exceeds_limit_blocked(self):
        for _ in range(5):
            await self.limiter.is_allowed("ip3:path", limit=5, window=60)
        ok, retry = await self.limiter.is_allowed("ip3:path", limit=5, window=60)
        assert ok is False
        assert retry > 0

    @pytest.mark.asyncio
    async def test_window_expiry_resets(self):
        """After the window passes, the bucket should refill."""
        for _ in range(3):
            await self.limiter.is_allowed("ip4:path", limit=3, window=1)
        # All 3 slots used — now wait
        await asyncio.sleep(1.1)
        ok, _ = await self.limiter.is_allowed("ip4:path", limit=3, window=1)
        assert ok is True

    @pytest.mark.asyncio
    async def test_different_keys_isolated(self):
        for _ in range(5):
            await self.limiter.is_allowed("ip5:path", limit=5, window=60)
        # ip6 is untouched
        ok, _ = await self.limiter.is_allowed("ip6:path", limit=5, window=60)
        assert ok is True


class TestResolveLimits:
    def test_search_route(self):
        limit, window = _resolve_limit("/search")
        assert limit == ROUTE_LIMITS["/search"][0]

    def test_research_route(self):
        limit, window = _resolve_limit("/research")
        assert limit == ROUTE_LIMITS["/research"][0]

    def test_crawl_route(self):
        limit, _ = _resolve_limit("/crawl")
        assert limit == ROUTE_LIMITS["/crawl"][0]

    def test_unknown_route_uses_default(self):
        limit, _ = _resolve_limit("/unknown-endpoint")
        assert limit == ROUTE_LIMITS["default"][0]

    def test_prefix_match(self):
        """Sub-paths should match the route prefix."""
        limit, _ = _resolve_limit("/search/advanced")
        assert limit == ROUTE_LIMITS["/search"][0]
