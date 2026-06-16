"""
Memory — stores conversation context and search history per session
Backed by Redis in production, in-memory dict for development
"""

import json
import time
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class Message:
    role: str           # "user" | "assistant"
    content: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class Session:
    session_id: str
    messages: List[Message] = field(default_factory=list)
    search_history: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class MemoryStore:
    """In-memory session store. Swap with RedisMemoryStore for production."""

    def __init__(self, max_messages: int = 20, ttl_seconds: int = 3600):
        self._sessions: Dict[str, Session] = {}
        self.max_messages = max_messages
        self.ttl_seconds = ttl_seconds

    def get_session(self, session_id: str) -> Session:
        session = self._sessions.get(session_id)
        if session is None:
            session = Session(session_id=session_id)
            self._sessions[session_id] = session
        return session

    def add_message(self, session_id: str, role: str, content: str):
        session = self.get_session(session_id)
        session.messages.append(Message(role=role, content=content))
        if len(session.messages) > self.max_messages:
            session.messages = session.messages[-self.max_messages:]
        session.updated_at = time.time()

    def add_search(self, session_id: str, query: str):
        session = self.get_session(session_id)
        if query not in session.search_history:
            session.search_history.append(query)
        session.updated_at = time.time()

    def get_context(self, session_id: str) -> List[Dict]:
        """Return messages in OpenAI-style format."""
        session = self.get_session(session_id)
        return [{"role": m.role, "content": m.content} for m in session.messages]

    def clear(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def evict_expired(self):
        now = time.time()
        expired = [sid for sid, s in self._sessions.items()
                   if now - s.updated_at > self.ttl_seconds]
        for sid in expired:
            del self._sessions[sid]
        if expired:
            logger.debug(f"Evicted {len(expired)} expired sessions")


class RedisMemoryStore:
    """Redis-backed memory store for production."""

    def __init__(self, redis_url: str, max_messages: int = 20, ttl_seconds: int = 3600):
        import redis.asyncio as aioredis
        self.redis = aioredis.from_url(redis_url, decode_responses=True)
        self.max_messages = max_messages
        self.ttl = ttl_seconds

    def _key(self, session_id: str) -> str:
        return f"session:{session_id}"

    async def get_session(self, session_id: str) -> Session:
        raw = await self.redis.get(self._key(session_id))
        if raw:
            data = json.loads(raw)
            msgs = [Message(**m) for m in data.get("messages", [])]
            return Session(
                session_id=session_id,
                messages=msgs,
                search_history=data.get("search_history", []),
                created_at=data.get("created_at", time.time()),
                updated_at=data.get("updated_at", time.time()),
            )
        return Session(session_id=session_id)

    async def save_session(self, session: Session):
        data = {
            "messages": [asdict(m) for m in session.messages],
            "search_history": session.search_history,
            "created_at": session.created_at,
            "updated_at": time.time(),
        }
        await self.redis.setex(self._key(session.session_id), self.ttl, json.dumps(data))

    async def add_message(self, session_id: str, role: str, content: str):
        session = await self.get_session(session_id)
        session.messages.append(Message(role=role, content=content))
        if len(session.messages) > self.max_messages:
            session.messages = session.messages[-self.max_messages:]
        await self.save_session(session)

    async def get_context(self, session_id: str) -> List[Dict]:
        session = await self.get_session(session_id)
        return [{"role": m.role, "content": m.content} for m in session.messages]

    async def clear(self, session_id: str):
        await self.redis.delete(self._key(session_id))


# Singleton — swap to RedisMemoryStore(settings.redis_url) in production
memory = MemoryStore()
