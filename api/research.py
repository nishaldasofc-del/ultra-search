"""
Research API — POST /research
Multi-agent deep research pipeline
"""

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import uuid

from llm.planner import ResearchPlanner
from llm.writer import ReportWriter
from llm.verifier import FactVerifier
from search.aggregator import SearchAggregator
from extractor.fetcher import ContentFetcher
from extractor.cleaner import ContentCleaner
from extractor.dedupe import Deduplicator

router = APIRouter()

# In-memory job store (use Redis in production)
_jobs: dict = {}


class ResearchRequest(BaseModel):
    query: str
    depth: int = 2          # 1=quick, 2=standard, 3=deep
    max_sources: int = 10
    fact_check: bool = True
    model: str = "deep"     # "fast" | "deep"


class ResearchJob(BaseModel):
    job_id: str
    status: str             # pending | running | done | failed
    query: str
    report: Optional[dict] = None
    error: Optional[str] = None


@router.post("", response_model=ResearchJob)
async def start_research(req: ResearchRequest, background_tasks: BackgroundTasks):
    """
    Start an async multi-agent research job.
    Returns a job_id to poll for results.
    """
    job_id = str(uuid.uuid4())
    _jobs[job_id] = ResearchJob(job_id=job_id, status="pending", query=req.query)
    background_tasks.add_task(_run_research, job_id, req)
    return _jobs[job_id]


@router.get("/{job_id}", response_model=ResearchJob)
async def get_research(job_id: str):
    """Poll research job status and results."""
    if job_id not in _jobs:
        raise HTTPException(404, "Job not found")
    return _jobs[job_id]


async def _run_research(job_id: str, req: ResearchRequest):
    """
    Full multi-agent pipeline:
    Planner → Search Agent → Verifier Agent → Writer Agent → JSON Report
    """
    try:
        _jobs[job_id].status = "running"

        # Stage 1: Planner breaks query into sub-queries
        planner = ResearchPlanner()
        plan = await planner.plan(req.query, depth=req.depth)

        # Stage 2: Search Agent fetches sources for each sub-query
        aggregator = SearchAggregator()
        fetcher = ContentFetcher()
        cleaner = ContentCleaner()
        deduper = Deduplicator()

        all_sources = []
        for sub_query in plan.sub_queries:
            results = await aggregator.search(sub_query, num_results=req.max_sources)
            for r in results:
                content = await fetcher.fetch(r["url"])
                if content:
                    r["content"] = cleaner.clean(content)
                all_sources.append(r)

        all_sources = deduper.deduplicate(all_sources)

        # Stage 3: Verifier cross-checks facts across sources
        verified_claims = []
        if req.fact_check:
            verifier = FactVerifier()
            verified_claims = await verifier.verify_sources(req.query, all_sources)

        # Stage 4: Writer compiles final report
        writer = ReportWriter()
        report = await writer.write(
            query=req.query,
            plan=plan,
            sources=all_sources,
            verified_claims=verified_claims,
        )

        _jobs[job_id].status = "done"
        _jobs[job_id].report = report

    except Exception as e:
        _jobs[job_id].status = "failed"
        _jobs[job_id].error = str(e)
