"""
Tests for memory.store — MemoryStore (in-memory)
"""

import pytest
import time
from memory.store import MemoryStore, Session, Message


class TestMemoryStore:
    def setup_method(self):
        self.store = MemoryStore(max_messages=5, ttl_seconds=60)

    def test_get_session_creates_fresh(self):
        s = self.store.get_session("new-session")
        assert s.session_id == "new-session"
        assert s.messages == []
        assert s.search_history == []

    def test_get_session_returns_same(self):
        s1 = self.store.get_session("abc")
        s2 = self.store.get_session("abc")
        assert s1 is s2

    def test_add_message_stored(self):
        self.store.add_message("s1", "user", "hello")
        ctx = self.store.get_context("s1")
        assert len(ctx) == 1
        assert ctx[0]["role"] == "user"
        assert ctx[0]["content"] == "hello"

    def test_add_multiple_roles(self):
        self.store.add_message("s2", "user", "ping")
        self.store.add_message("s2", "assistant", "pong")
        ctx = self.store.get_context("s2")
        assert ctx[0]["role"] == "user"
        assert ctx[1]["role"] == "assistant"

    def test_max_messages_respected(self):
        for i in range(10):
            self.store.add_message("s3", "user", f"msg {i}")
        ctx = self.store.get_context("s3")
        assert len(ctx) == 5  # max_messages=5
        assert ctx[-1]["content"] == "msg 9"  # newest retained

    def test_add_search(self):
        self.store.add_search("s4", "python tutorial")
        s = self.store.get_session("s4")
        assert "python tutorial" in s.search_history

    def test_add_search_no_duplicates(self):
        self.store.add_search("s5", "same query")
        self.store.add_search("s5", "same query")
        s = self.store.get_session("s5")
        assert s.search_history.count("same query") == 1

    def test_clear_removes_session(self):
        self.store.add_message("s6", "user", "hi")
        self.store.clear("s6")
        # After clearing, a fresh session is returned
        ctx = self.store.get_context("s6")
        assert ctx == []

    def test_clear_nonexistent_no_error(self):
        self.store.clear("does-not-exist")  # should not raise

    def test_evict_expired(self):
        store = MemoryStore(ttl_seconds=1)
        store.add_message("expiring", "user", "bye")
        time.sleep(1.1)
        store.evict_expired()
        # Session gone — fresh one returned
        assert store.get_context("expiring") == []

    def test_evict_leaves_active(self):
        store = MemoryStore(ttl_seconds=10)
        store.add_message("active", "user", "stay")
        store.evict_expired()
        assert store.get_context("active") != []

    def test_updated_at_changes_on_message(self):
        self.store.add_message("s7", "user", "first")
        t1 = self.store.get_session("s7").updated_at
        time.sleep(0.05)
        self.store.add_message("s7", "user", "second")
        t2 = self.store.get_session("s7").updated_at
        assert t2 > t1
