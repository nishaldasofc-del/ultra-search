"""add seed_urls table and tsvector column

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import TSVECTOR

revision      = "0002"
down_revision = "0001"
branch_labels = None
depends_on    = None


def upgrade() -> None:
    # Add search_vector + indexed_at + lang columns to pages
    op.add_column("pages", sa.Column("search_vector", TSVECTOR, nullable=True))
    op.add_column("pages", sa.Column("indexed_at",   sa.DateTime(), nullable=True))
    op.add_column("pages", sa.Column("lang",         sa.String(8),  server_default="en"))

    # GIN index for fast FTS
    op.create_index(
        "ix_pages_search_vector", "pages", ["search_vector"],
        postgresql_using="gin",
    )

    # Tsvector auto-update trigger
    op.execute("""
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

    # Backfill existing rows
    op.execute("""
        UPDATE pages SET
            search_vector =
                setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
                setweight(to_tsvector('english', coalesce(content, '')), 'B')
        WHERE search_vector IS NULL;
    """)

    # seed_urls table
    op.create_table(
        "seed_urls",
        sa.Column("id",           sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("url",          sa.String(2048), unique=True, nullable=False),
        sa.Column("max_depth",    sa.Integer(),    server_default="3"),
        sa.Column("max_pages",    sa.Integer(),    server_default="200"),
        sa.Column("active",       sa.Boolean(),    server_default="true"),
        sa.Column("last_crawled", sa.DateTime(),   nullable=True),
        sa.Column("crawl_count",  sa.Integer(),    server_default="0"),
        sa.Column("added_at",     sa.DateTime(),   server_default=sa.func.now()),
    )
    op.create_index("ix_seed_urls_url", "seed_urls", ["url"], unique=True)


def downgrade() -> None:
    op.drop_table("seed_urls")
    op.execute("DROP TRIGGER IF EXISTS tsvector_update ON pages;")
    op.execute("DROP FUNCTION IF EXISTS update_pages_search_vector;")
    op.drop_index("ix_pages_search_vector", table_name="pages")
    op.drop_column("pages", "lang")
    op.drop_column("pages", "indexed_at")
    op.drop_column("pages", "search_vector")
