"""
Memory/Session API — manage conversation sessions
GET  /memory/{session_id}
POST /memory/{session_id}/message
DELETE /memory/{session_id}
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from memory.store import memory

router = APIRouter()


class AddMessageRequest(BaseModel):
    role: str       # "user" | "assistant"
    content: str


class ContextResponse(BaseModel):
    session_id: str
    messages: List[dict]
    search_history: List[str]


@router.get("/{session_id}", response_model=ContextResponse)
async def get_session(session_id: str):
    session = memory.get_session(session_id)
    return ContextResponse(
        session_id=session_id,
        messages=memory.get_context(session_id),
        search_history=session.search_history,
    )


@router.post("/{session_id}/message")
async def add_message(session_id: str, req: AddMessageRequest):
    if req.role not in ("user", "assistant"):
        raise HTTPException(400, "role must be 'user' or 'assistant'")
    memory.add_message(session_id, req.role, req.content)
    return {"status": "ok", "session_id": session_id}


@router.delete("/{session_id}")
async def clear_session(session_id: str):
    memory.clear(session_id)
    return {"status": "cleared", "session_id": session_id}
