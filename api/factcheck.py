"""
Fact-Check API — POST /fact-check
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from factcheck.checker import FactChecker

router = APIRouter()


class FactCheckRequest(BaseModel):
    claim: str
    num_sources: int = 8


class FactCheckResponse(BaseModel):
    claim: str
    confidence: float       # 0.0 – 1.0
    verified: bool
    evidence: str
    sources: List[dict]


@router.post("", response_model=FactCheckResponse)
async def fact_check(req: FactCheckRequest):
    if not req.claim.strip():
        raise HTTPException(400, "Claim cannot be empty")

    checker = FactChecker()
    result = await checker.check(req.claim)
    return FactCheckResponse(**result)
