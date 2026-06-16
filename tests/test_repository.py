"""
Tests for database.repository — PageRepository + ReportRepository
Uses mocked AsyncSession (no live DB required).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


def _make_mock_session():
    session = MagicMock()
    session.execute = AsyncMock()
    session.commit  = AsyncMock()
    session.refresh = AsyncMock()
    session.add     = MagicMock()
    return session


# ── PageRepository ────────────────────────────────────────────────────────────
class TestPageRepository:
    def setup_method(self):
        from database.repository import PageRepository
        self.session = _make_mock_session()
        self.repo = PageRepository(self.session)

    @pytest.mark.asyncio
    async def test_upsert_creates_new_page(self):
        # get_by_url returns None → new page
        self.session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)

        page = await self.repo.upsert(
            url="https://example.com",
            domain="example.com",
            title="Example",
            content="Hello world",
            word_count=2,
        )
        self.session.add.assert_called_once()
        self.session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(self):
        from database.models import Page
        existing = Page(
            url="https://example.com", domain="example.com",
            title="Old Title", content="old", word_count=1,
        )
        self.session.execute.return_value.scalar_one_or_none = MagicMock(return_value=existing)

        result = await self.repo.upsert(
            url="https://example.com",
            domain="example.com",
            title="New Title",
            content="new content",
            word_count=2,
        )
        assert result.title == "New Title"
        self.session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_get_by_url_returns_none(self):
        self.session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
        result = await self.repo.get_by_url("https://missing.com")
        assert result is None

    @pytest.mark.asyncio
    async def test_count_returns_integer(self):
        self.session.execute.return_value.scalar = MagicMock(return_value=42)
        count = await self.repo.count()
        assert count == 42


# ── ReportRepository ──────────────────────────────────────────────────────────
class TestReportRepository:
    def setup_method(self):
        from database.repository import ReportRepository
        self.session = _make_mock_session()
        self.repo = ReportRepository(self.session)

    @pytest.mark.asyncio
    async def test_create_report(self):
        from database.models import ResearchReport
        report_obj = ResearchReport(job_id="job-1", query="test query", status="pending")
        self.session.refresh = AsyncMock(return_value=None)

        # Patch add so it returns the report_obj
        created_reports = []
        def _add(obj):
            created_reports.append(obj)
        self.session.add = MagicMock(side_effect=_add)

        await self.repo.create("job-1", "test query")
        self.session.add.assert_called_once()
        self.session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_update_status(self):
        self.session.execute = AsyncMock()
        await self.repo.update_status("job-1", "done", report={"title": "Report"})
        self.session.execute.assert_called_once()
        self.session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_get_returns_none_for_missing(self):
        self.session.execute.return_value.scalar_one_or_none = MagicMock(return_value=None)
        result = await self.repo.get("nonexistent-job")
        assert result is None
