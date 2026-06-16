"""
Tests for GET/POST/DELETE /memory/{session_id}
"""

import pytest


SESSION_ID = "test-session-abc123"


@pytest.mark.asyncio
async def test_memory_get_fresh_session(client):
    resp = await client.get(f"/memory/{SESSION_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["session_id"] == SESSION_ID
    assert data["messages"] == []
    assert isinstance(data["search_history"], list)


@pytest.mark.asyncio
async def test_memory_add_message(client):
    resp = await client.post(
        f"/memory/{SESSION_ID}/message",
        json={"role": "user", "content": "Hello, Ultra Search!"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_memory_message_persists(client):
    sid = "persist-session-999"
    await client.post(f"/memory/{sid}/message", json={"role": "user", "content": "ping"})
    resp = await client.get(f"/memory/{sid}")
    data = resp.json()
    assert any(m["content"] == "ping" for m in data["messages"])


@pytest.mark.asyncio
async def test_memory_invalid_role_400(client):
    resp = await client.post(
        f"/memory/{SESSION_ID}/message",
        json={"role": "system", "content": "injected"},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_memory_clear_session(client):
    sid = "clear-me-session"
    await client.post(f"/memory/{sid}/message", json={"role": "user", "content": "bye"})
    del_resp = await client.delete(f"/memory/{sid}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "cleared"

    # After clearing, session should be fresh
    resp = await client.get(f"/memory/{sid}")
    assert resp.json()["messages"] == []


@pytest.mark.asyncio
async def test_memory_assistant_role_accepted(client):
    sid = "assistant-session"
    resp = await client.post(
        f"/memory/{sid}/message",
        json={"role": "assistant", "content": "I can help with that."},
    )
    assert resp.status_code == 200
