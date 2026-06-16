"""
Alembic env.py — async-aware, reads DB URL from app settings.
Supports both offline (SQL script generation) and online (live migration) modes.
"""

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ── project root on path ─────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── app imports ───────────────────────────────────────────────────────────────
from config import settings          # noqa: E402
from database.models import Base     # noqa: E402

# ── alembic config ────────────────────────────────────────────────────────────
config = context.config

# Wire up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override DB URL from settings so we never hard-code creds in alembic.ini
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
_url = clean_postgres_url(settings.postgres_url)
config.set_main_option("sqlalchemy.url", _url)

# Autogenerate support: point at our models' metadata
target_metadata = Base.metadata


# ─────────────────────────────────────────────────────────────────────────────
# OFFLINE mode — emit SQL to stdout without a live DB connection
# ─────────────────────────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    """Generate migration SQL without a live DB (useful for review / CI)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ─────────────────────────────────────────────────────────────────────────────
# ONLINE mode — run against a live DB using async engine
# ─────────────────────────────────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations inside a sync connection wrapper."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ─────────────────────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
