"""
Rate Limiting Middleware — sliding-window per IP
Falls back to in-memory dict when Redis is unavailable
"""

import time
import asyncio
from collections import defaultdict
from typing import Dict, Tuple
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# route_prefix → (max_requests, window_seconds)
ROUTE_LIMITS: Dict[str, Tuple[int, int]] = {
    "/search":         (60,  60),
    "/research":       (10,  60),
    "/crawl":          (5,   60),
    "/fact-check":     (20,  60),
    "/vector-search":  (60,  60),
    "default":         (120, 60),
}


class InMemoryRateLimiter:
    def __init__(self):
        self._buckets: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def is_allowed(self, key: str, limit: int, window: int) -> Tuple[bool, int]:
        async with self._lock:
            now = time.time()
            self._buckets[key] = [t for t in self._buckets[key] if now - t < window]
            if len(self._buckets[key]) >= limit:
                oldest = self._buckets[key][0]
                retry_after = int(window - (now - oldest)) + 1
                return False, retry_after
            self._buckets[key].append(now)
            return True, 0


_limiter = InMemoryRateLimiter()


def _resolve_limit(path: str) -> Tuple[int, int]:
    for prefix, limits in ROUTE_LIMITS.items():
        if prefix != "default" and path.startswith(prefix):
            return limits
    return ROUTE_LIMITS["default"]


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        ip = (request.client.host if request.client else "unknown")
        path = request.url.path
        limit, window = _resolve_limit(path)

        allowed, retry_after = await _limiter.is_allowed(f"{ip}:{path}", limit, window)
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": retry_after},
                headers={"Retry-After": str(retry_after)},
            )

        return await call_next(request)
