"""
Database migrations — run once on startup or via CLI
Usage: python -m database.migrations
"""

import asyncio
import logging
from database.models import engine, Base

logger = logging.getLogger(__name__)


async def run_migrations():
    """Create all tables if they don't exist."""
    logger.info("Running database migrations...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Migrations complete.")


async def drop_all():
    """Drop all tables. Destructive — use only in dev/test."""
    logger.warning("Dropping all tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    logger.warning("All tables dropped.")


if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "migrate"
    if cmd == "migrate":
        asyncio.run(run_migrations())
    elif cmd == "drop":
        asyncio.run(drop_all())
    else:
        print(f"Unknown command: {cmd}. Use 'migrate' or 'drop'.")
