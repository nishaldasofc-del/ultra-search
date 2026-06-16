"""
ULTRA SEARCH ENGINE — Main Application Entry Point
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from utils.logging import setup_logging

# ── routers ───────────────────────────────────────────────────────────────────
from api.search        import router as search_router
from api.research      import router as research_router
from api.crawl         import router as crawl_router
from api.factcheck     import router as factcheck_router
from api.memory        import router as memory_router

# ── middleware ────────────────────────────────────────────────────────────────
from middleware.rate_limit import RateLimitMiddleware

setup_logging(level="INFO")
logger = logging.getLogger(__name__)


# ── lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Ultra Search Engine starting up...")
    # DB tables (idempotent — safe to run every boot in dev)
    try:
        from database.models import init_db
        await init_db()
        logger.info("Database tables verified.")
    except Exception as e:
        logger.warning(f"DB init skipped (no DB available): {e}")
    yield
    logger.info("Ultra Search Engine shutting down.")


# ── app ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Ultra Search Engine",
    description=(
        "AI-powered search with multi-agent research, "
        "crawling, fact-checking, vector search, and session memory."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting (before routing)
app.add_middleware(RateLimitMiddleware)

# ── routes ────────────────────────────────────────────────────────────────────
app.include_router(search_router,        prefix="/search",        tags=["Search"])
app.include_router(research_router,      prefix="/research",      tags=["Research"])
app.include_router(crawl_router,         prefix="/crawl",         tags=["Crawl"])
app.include_router(factcheck_router,     prefix="/fact-check",    tags=["Fact Check"])
app.include_router(memory_router,        prefix="/memory",        tags=["Memory"])


# ── health ────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": "1.0.0"}
