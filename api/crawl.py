"""
Crawl API — POST /crawl   GET /crawl/{job_id}
Also: POST /crawl/seeds  GET /crawl/seeds  DELETE /crawl/seeds/{url}
"""

import asyncio
import uuid
import logging
from typing import Dict, Optional, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from indexer.pipeline   import IndexPipeline
from indexer.scheduler  import add_seed, remove_seed, list_seeds

logger  = logging.getLogger(__name__)
router  = APIRouter()

# In-memory job store (replace with Redis for multi-instance)
_jobs: Dict[str, dict] = {}


# ── Request / Response Models ─────────────────────────────────────────────────

class CrawlRequest(BaseModel):
    url:       str
    max_depth: int  = Field(default=3, ge=1, le=6)
    max_pages: int  = Field(default=200, ge=1, le=2000)
    add_seed:  bool = False   # also add to continuous re-crawl schedule


class SeedRequest(BaseModel):
    url:       str
    max_depth: int = 3
    max_pages: int = 200


# ── Background job ────────────────────────────────────────────────────────────

async def _run_index_job(job_id: str, url: str, max_depth: int, max_pages: int):
    _jobs[job_id]["status"] = "running"
    try:
        pipeline = IndexPipeline(
            max_depth=max_depth,
            max_pages=max_pages,
        )
        summary = await pipeline.run(url, job_id=job_id)
        _jobs[job_id].update({
            "status":        "done",
            "pages_indexed": summary["indexed"],
            "pages_failed":  summary["failed"],
            "pages_skipped": summary["skipped"],
        })
    except Exception as e:
        logger.exception(f"Index job {job_id} failed: {e}")
        _jobs[job_id].update({"status": "failed", "error": str(e)})


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("")
async def crawl(req: CrawlRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id":        job_id,
        "url":           req.url,
        "status":        "pending",
        "pages_indexed": 0,
        "pages_failed":  0,
        "pages_skipped": 0,
        "errors":        [],
    }

    if req.add_seed:
        await add_seed(req.url, max_depth=req.max_depth, max_pages=req.max_pages)

    background_tasks.add_task(
        _run_index_job, job_id, req.url, req.max_depth, req.max_pages
    )
    return _jobs[job_id]


@router.get("/{job_id}")
async def get_crawl_job(job_id: str):
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, f"Job {job_id!r} not found")
    return job


# ── Seed management ───────────────────────────────────────────────────────────

@router.post("/seeds")
async def create_seed(req: SeedRequest):
    """Add a URL to the continuous re-crawl schedule."""
    await add_seed(req.url, max_depth=req.max_depth, max_pages=req.max_pages)
    return {"status": "added", "url": req.url}


@router.get("/seeds")
async def get_seeds():
    """List all seed URLs and their crawl status."""
    seeds = await list_seeds()
    return {"seeds": seeds, "total": len(seeds)}


@router.delete("/seeds/{url:path}")
async def delete_seed(url: str):
    """Deactivate a seed URL."""
    await remove_seed(url)
    return {"status": "deactivated", "url": url}
