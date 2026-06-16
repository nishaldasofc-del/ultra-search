"""
Database — SQLAlchemy async models
Added: full-text search index on pages, SeedURL table
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import (
    String, Text, Float, Integer, DateTime, Boolean, JSON, Index
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from datetime import datetime
from config import settings

from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode

def clean_postgres_url(url: str) -> str:
    # 1. Normalize the schema for asyncpg
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    # 2. Parse query parameters
    parsed = urlparse(url)
    query_params = dict(parse_qsl(parsed.query))

    # 3. Convert sslmode to ssl
    if "sslmode" in query_params:
        val = query_params.pop("sslmode")
        if val in ("require", "prefer", "allow"):
            query_params["ssl"] = "true"

    # 4. Strip completely unsupported asyncpg parameters
    unsupported = ["channel_binding", "sslrootcert", "sslcert", "sslkey", "sslcrl"]
    for param in unsupported:
        query_params.pop(param, None)

    # 5. Reconstruct the clean URL
    new_query = urlencode(query_params)
    return urlunparse(parsed._replace(query=new_query))

# Apply the normalizer
_db_url = clean_postgres_url(settings.postgres_url)

engine       = create_async_engine(_db_url, echo=False, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


class Page(Base):
    __tablename__ = "pages"

    id:          Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    url:         Mapped[str]      = mapped_column(String(2048), unique=True, index=True)
    domain:      Mapped[str]      = mapped_column(String(256), index=True)
    title:       Mapped[str]      = mapped_column(String(512), nullable=True)
    content:     Mapped[str]      = mapped_column(Text, nullable=True)
    word_count:  Mapped[int]      = mapped_column(Integer, default=0)
    crawled_at:  Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    indexed_at:  Mapped[datetime] = mapped_column(DateTime, nullable=True)
    depth:       Mapped[int]      = mapped_column(Integer, default=0)
    status_code: Mapped[int]      = mapped_column(Integer, nullable=True)
    lang:        Mapped[str]      = mapped_column(String(8), default="en")
    # Populated by a DB trigger / UPDATE after insert
    search_vector: Mapped[str]   = mapped_column(TSVECTOR, nullable=True)

    __table_args__ = (
        # GIN index on the tsvector column — makes FTS fast
        Index("ix_pages_search_vector", "search_vector", postgresql_using="gin"),
    )


class CrawlQueue(Base):
    __tablename__ = "crawl_queue"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    url:        Mapped[str]      = mapped_column(String(2048), unique=True)
    depth:      Mapped[int]      = mapped_column(Integer, default=0)
    priority:   Mapped[float]    = mapped_column(Float, default=0.0)
    locked:     Mapped[bool]     = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SeedURL(Base):
    """
    Domains/URLs that the indexer continuously re-crawls.
    Add entries here to grow your index.
    """
    __tablename__ = "seed_urls"

    id:           Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    url:          Mapped[str]      = mapped_column(String(2048), unique=True)
    max_depth:    Mapped[int]      = mapped_column(Integer, default=3)
    max_pages:    Mapped[int]      = mapped_column(Integer, default=200)
    active:       Mapped[bool]     = mapped_column(Boolean, default=True)
    last_crawled: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    crawl_count:  Mapped[int]      = mapped_column(Integer, default=0)
    added_at:     Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ResearchReport(Base):
    __tablename__ = "research_reports"

    id:         Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id:     Mapped[str]      = mapped_column(String(64), unique=True, index=True)
    query:      Mapped[str]      = mapped_column(Text)
    report:     Mapped[dict]     = mapped_column(JSON, nullable=True)
    status:     Mapped[str]      = mapped_column(String(32), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create tsvector update trigger (idempotent)
        await conn.execute(
            __import__("sqlalchemy").text("""
            CREATE OR REPLACE FUNCTION update_pages_search_vector()
            RETURNS trigger AS $$
            BEGIN
                NEW.search_vector :=
                    setweight(to_tsvector('english', coalesce(NEW.title, '')), 'A') ||
                    setweight(to_tsvector('english', coalesce(NEW.content, '')), 'B');
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;

            DROP TRIGGER IF EXISTS tsvector_update ON pages;
            CREATE TRIGGER tsvector_update
                BEFORE INSERT OR UPDATE OF title, content
                ON pages
                FOR EACH ROW EXECUTE FUNCTION update_pages_search_vector();
            """)
        )


async def get_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
