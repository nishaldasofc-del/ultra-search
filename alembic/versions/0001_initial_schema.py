"""initial schema

Revision ID: 0001
Revises: 
Create Date: 2026-06-15

Creates: pages, crawl_queue, research_reports
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── pages ─────────────────────────────────────────────────────────────────
    op.create_table(
        "pages",
        sa.Column("id",           sa.Integer(),       primary_key=True, autoincrement=True),
        sa.Column("url",          sa.String(2048),    nullable=False, unique=True),
        sa.Column("domain",       sa.String(256),     nullable=False),
        sa.Column("title",        sa.String(512),     nullable=True),
        sa.Column("content",      sa.Text(),          nullable=True),
        sa.Column("word_count",   sa.Integer(),       nullable=False, server_default="0"),
        sa.Column("crawled_at",   sa.DateTime(),      nullable=False, server_default=sa.func.now()),
        sa.Column("depth",        sa.Integer(),       nullable=False, server_default="0"),
        sa.Column("status_code",  sa.Integer(),       nullable=True),
    )
    op.create_index("ix_pages_url",    "pages", ["url"],    unique=True)
    op.create_index("ix_pages_domain", "pages", ["domain"], unique=False)

    # ── crawl_queue ───────────────────────────────────────────────────────────
    op.create_table(
        "crawl_queue",
        sa.Column("id",         sa.Integer(),   primary_key=True, autoincrement=True),
        sa.Column("url",        sa.String(2048), nullable=False, unique=True),
        sa.Column("depth",      sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("priority",   sa.Float(),     nullable=False, server_default="0.0"),
        sa.Column("locked",     sa.Boolean(),   nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(),  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_crawl_queue_priority", "crawl_queue", ["priority", "locked"])

    # ── research_reports ──────────────────────────────────────────────────────
    op.create_table(
        "research_reports",
        sa.Column("id",         sa.Integer(),   primary_key=True, autoincrement=True),
        sa.Column("job_id",     sa.String(64),  nullable=False, unique=True),
        sa.Column("query",      sa.Text(),      nullable=False),
        sa.Column("report",     sa.JSON(),      nullable=True),
        sa.Column("status",     sa.String(32),  nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(),  nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_research_reports_job_id", "research_reports", ["job_id"], unique=True)


def downgrade() -> None:
    op.drop_table("research_reports")
    op.drop_table("crawl_queue")
    op.drop_table("pages")
