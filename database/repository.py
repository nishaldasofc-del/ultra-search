"""
Repository — data access layer for DB models
Keeps SQL out of business logic
"""

from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from database.models import Page, CrawlQueue, ResearchReport
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert(self, url: str, domain: str, title: str = "",
                     content: str = "", word_count: int = 0, depth: int = 0) -> Page:
        existing = await self.get_by_url(url)
        if existing:
            existing.title = title
            existing.content = content
            existing.word_count = word_count
            existing.crawled_at = datetime.utcnow()
            await self.session.commit()
            return existing

        page = Page(url=url, domain=domain, title=title,
                    content=content, word_count=word_count, depth=depth)
        self.session.add(page)
        await self.session.commit()
        await self.session.refresh(page)
        return page

    async def get_by_url(self, url: str) -> Optional[Page]:
        result = await self.session.execute(select(Page).where(Page.url == url))
        return result.scalar_one_or_none()

    async def get_by_domain(self, domain: str, limit: int = 100) -> List[Page]:
        result = await self.session.execute(
            select(Page).where(Page.domain == domain).limit(limit)
        )
        return list(result.scalars())

    async def count(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(select(func.count(Page.id)))
        return result.scalar()


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, job_id: str, query: str) -> ResearchReport:
        report = ResearchReport(job_id=job_id, query=query, status="pending")
        self.session.add(report)
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def update_status(self, job_id: str, status: str, report: dict = None):
        values = {"status": status}
        if report is not None:
            values["report"] = report
        await self.session.execute(
            update(ResearchReport)
            .where(ResearchReport.job_id == job_id)
            .values(**values)
        )
        await self.session.commit()

    async def get(self, job_id: str) -> Optional[ResearchReport]:
        result = await self.session.execute(
            select(ResearchReport).where(ResearchReport.job_id == job_id)
        )
        return result.scalar_one_or_none()
