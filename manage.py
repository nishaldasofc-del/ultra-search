#!/usr/bin/env python3
"""
manage.py — Ultra Search Engine CLI management script

Usage:
  python manage.py <command> [options]

Commands:
  db migrate          Run Alembic migrations (upgrade head)
  db downgrade <rev>  Downgrade to a specific revision (or 'base')
  db revision <msg>   Auto-generate a new migration from model changes
  db history          Show migration history
  db current          Show current DB revision

  server              Start the FastAPI server with uvicorn
  worker              Start a Celery worker
  beat                Start Celery beat scheduler
  worker-health       Start the worker health-check sidecar

  crawl <url>         Enqueue a crawl job via the API (requires server running)
  search <query>      Run a quick search and print results
  factcheck <claim>   Quick fact-check via the API

  shell               Drop into an async Python REPL with app context loaded

  help                Show this message
"""

import argparse
import asyncio
import json
import os
import sys

# ── ensure project root is on PYTHONPATH ─────────────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ═════════════════════════════════════════════════════════════════════════════
# DB commands
# ═════════════════════════════════════════════════════════════════════════════

def cmd_db(args):
    """Dispatcher for all `db` sub-commands."""
    sub = args.sub if hasattr(args, "sub") else None

    if sub == "migrate" or sub is None:
        _db_migrate()
    elif sub == "downgrade":
        _db_downgrade(args.revision)
    elif sub == "revision":
        _db_revision(args.message)
    elif sub == "history":
        _db_history()
    elif sub == "current":
        _db_current()
    else:
        print(f"Unknown db sub-command: {sub}")
        sys.exit(1)


def _alembic_cfg():
    from alembic.config import Config
    cfg = Config(os.path.join(ROOT, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(ROOT, "alembic"))
    return cfg


def _db_migrate():
    from alembic import command
    print("Running migrations → head …")
    command.upgrade(_alembic_cfg(), "head")
    print("✓ Migrations complete.")


def _db_downgrade(revision: str):
    from alembic import command
    print(f"Downgrading to revision: {revision} …")
    command.downgrade(_alembic_cfg(), revision)
    print("✓ Downgrade complete.")


def _db_revision(message: str):
    from alembic import command
    print(f"Generating migration: '{message}' …")
    command.revision(_alembic_cfg(), autogenerate=True, message=message)
    print("✓ Migration file created in alembic/versions/")


def _db_history():
    from alembic import command
    command.history(_alembic_cfg(), verbose=True)


def _db_current():
    from alembic import command
    command.current(_alembic_cfg(), verbose=True)


# ═════════════════════════════════════════════════════════════════════════════
# Server / worker commands
# ═════════════════════════════════════════════════════════════════════════════

def cmd_server(args):
    import uvicorn
    host = getattr(args, "host", "0.0.0.0")
    port = int(getattr(args, "port", 8000))
    reload = getattr(args, "reload", False)
    print(f"Starting Ultra Search Engine on http://{host}:{port} (reload={reload})")
    uvicorn.run("app:app", host=host, port=port, reload=reload)


def cmd_worker(args):
    from workers.tasks import celery_app
    loglevel = getattr(args, "loglevel", "info")
    concurrency = getattr(args, "concurrency", 4)
    print(f"Starting Celery worker (concurrency={concurrency}, loglevel={loglevel})")
    celery_app.worker_main([
        "worker",
        f"--loglevel={loglevel}",
        f"--concurrency={concurrency}",
        "--pool=prefork",
    ])


def cmd_beat(args):
    from workers.beat import beat_app
    loglevel = getattr(args, "loglevel", "info")
    print("Starting Celery beat scheduler …")
    beat_app.start(argv=["beat", f"--loglevel={loglevel}"])


def cmd_worker_health(args):
    import uvicorn
    port = int(getattr(args, "port", 8001))
    print(f"Starting worker health-check on http://0.0.0.0:{port}/health")
    uvicorn.run("workers.health:app", host="0.0.0.0", port=port)


# ═════════════════════════════════════════════════════════════════════════════
# Quick-fire API helpers (require server to be running)
# ═════════════════════════════════════════════════════════════════════════════

BASE_URL = os.getenv("ULTRA_SEARCH_URL", "http://localhost:8000")


def _post(path, payload):
    import httpx
    resp = httpx.post(f"{BASE_URL}{path}", json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()


def cmd_crawl(args):
    data = _post("/crawl", {
        "url": args.url,
        "max_depth": args.depth,
        "max_pages": args.pages,
    })
    print(json.dumps(data, indent=2))


def cmd_search(args):
    data = _post("/search", {
        "query": " ".join(args.query),
        "num_results": args.num,
        "extract_content": False,
        "summarize": True,
    })
    print(f"\n{'─'*60}")
    print(f"Query: {data['query']}")
    print(f"{'─'*60}")
    if data.get("summary"):
        print(f"\nSummary:\n{data['summary']}\n")
    for i, r in enumerate(data["results"], 1):
        print(f"{i}. {r['title']}")
        print(f"   {r['url']}")
        print(f"   {r['snippet'][:120]}…\n")


def cmd_factcheck(args):
    data = _post("/fact-check", {"claim": " ".join(args.claim)})
    verdict = "✓ VERIFIED" if data["verified"] else "✗ NOT VERIFIED"
    print(f"\nClaim: {data['claim']}")
    print(f"Verdict: {verdict}  (confidence: {data['confidence']:.0%})")
    print(f"Evidence: {data['evidence']}")
    print(f"\nSources ({len(data['sources'])}):")
    for s in data["sources"]:
        print(f"  • {s.get('url', s.get('title', '?'))}")


# ═════════════════════════════════════════════════════════════════════════════
# Shell
# ═════════════════════════════════════════════════════════════════════════════

def cmd_shell(_args):
    """Drop into an async REPL with app context pre-loaded."""
    try:
        import IPython
        from traitlets.config import Config as IPyConfig
        c = IPyConfig()
        c.InteractiveShellApp.exec_lines = [
            "import asyncio",
            "from config import settings",
            "from database.models import engine, SessionLocal",
            "from database.repository import PageRepository, ReportRepository",
            "from memory.store import memory",
            "print('Ultra Search shell ready. `settings`, `engine`, `memory` available.')",
        ]
        IPython.start_ipython(argv=[], config=c)
    except ImportError:
        print("IPython not installed — falling back to stdlib REPL")
        import code
        import readline  # noqa: F401 — enables arrow-key history
        from config import settings  # noqa: F401
        code.interact(
            banner="Ultra Search shell. `settings` available. Ctrl-D to exit.",
            local={"settings": settings},
        )


# ═════════════════════════════════════════════════════════════════════════════
# Argument parser
# ═════════════════════════════════════════════════════════════════════════════

def build_parser():
    p = argparse.ArgumentParser(
        prog="manage.py",
        description="Ultra Search Engine management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="command")

    # ── db ────────────────────────────────────────────────────────────────────
    db_p = sub.add_parser("db", help="Database migration commands")
    db_sub = db_p.add_subparsers(dest="sub")

    db_sub.add_parser("migrate",   help="Run migrations to head")

    down_p = db_sub.add_parser("downgrade", help="Downgrade to a revision")
    down_p.add_argument("revision", help="Target revision ID or 'base'")

    rev_p = db_sub.add_parser("revision", help="Auto-generate a new migration")
    rev_p.add_argument("message", help="Migration message / description")

    db_sub.add_parser("history", help="Show migration history")
    db_sub.add_parser("current", help="Show current revision")

    # ── server ────────────────────────────────────────────────────────────────
    srv_p = sub.add_parser("server", help="Start FastAPI server")
    srv_p.add_argument("--host",   default="0.0.0.0")
    srv_p.add_argument("--port",   default=8000, type=int)
    srv_p.add_argument("--reload", action="store_true", help="Hot-reload (dev only)")

    # ── worker ────────────────────────────────────────────────────────────────
    wrk_p = sub.add_parser("worker", help="Start Celery worker")
    wrk_p.add_argument("--loglevel",   default="info")
    wrk_p.add_argument("--concurrency", default=4, type=int)

    # ── beat ──────────────────────────────────────────────────────────────────
    beat_p = sub.add_parser("beat", help="Start Celery beat")
    beat_p.add_argument("--loglevel", default="info")

    # ── worker-health ─────────────────────────────────────────────────────────
    wh_p = sub.add_parser("worker-health", help="Start worker health sidecar")
    wh_p.add_argument("--port", default=8001, type=int)

    # ── crawl ─────────────────────────────────────────────────────────────────
    cr_p = sub.add_parser("crawl", help="Enqueue a crawl job")
    cr_p.add_argument("url")
    cr_p.add_argument("--depth", default=2,   type=int)
    cr_p.add_argument("--pages", default=100, type=int)

    # ── search ────────────────────────────────────────────────────────────────
    sr_p = sub.add_parser("search", help="Quick search")
    sr_p.add_argument("query", nargs="+")
    sr_p.add_argument("--num", default=5, type=int)

    # ── factcheck ─────────────────────────────────────────────────────────────
    fc_p = sub.add_parser("factcheck", help="Quick fact-check")
    fc_p.add_argument("claim", nargs="+")

    # ── shell ─────────────────────────────────────────────────────────────────
    sub.add_parser("shell", help="Interactive Python shell with app context")

    return p


# ═════════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════════

# ═════════════════════════════════════════════════════════════════════════════
# Index / Seed commands (added for zero-dependency search)
# ═════════════════════════════════════════════════════════════════════════════

def cmd_index(args):
    """Immediately crawl and index a URL."""
    import asyncio
    from indexer.pipeline import IndexPipeline

    async def _run():
        pipeline = IndexPipeline(
            max_depth=args.depth,
            max_pages=args.pages,
        )
        summary = await pipeline.run(args.url)
        print(f"\n✓ Indexed {summary['indexed']} pages from {args.url}")
        print(f"  Failed:  {summary['failed']}")
        print(f"  Skipped: {summary['skipped']}")

    asyncio.run(_run())


def cmd_seeds(args):
    """Manage seed URLs."""
    import asyncio
    from indexer.scheduler import add_seed, remove_seed, list_seeds

    async def _run():
        sub = getattr(args, "seed_sub", None)
        if sub == "add":
            await add_seed(args.url, max_depth=args.depth, max_pages=args.pages)
            print(f"✓ Seed added: {args.url}")
        elif sub == "remove":
            await remove_seed(args.url)
            print(f"✓ Seed deactivated: {args.url}")
        elif sub == "list" or sub is None:
            seeds = await list_seeds()
            if not seeds:
                print("No seeds yet. Add one with: manage.py seeds add <url>")
                return
            print(f"\n{'URL':<50} {'Active':<8} {'Crawls':<8} {'Last Crawled'}")
            print("─" * 90)
            for s in seeds:
                last = str(s["last_crawled"])[:16] if s["last_crawled"] else "never"
                print(f"{s['url'][:49]:<50} {str(s['active']):<8} {s['crawl_count']:<8} {last}")

    asyncio.run(_run())


def cmd_index_stats(_args):
    """Print index stats: pages in PostgreSQL."""
    import asyncio
    from database.models import SessionLocal
    from sqlalchemy import text

    async def _run():
        async with SessionLocal() as session:
            r = await session.execute(
                text("SELECT COUNT(*) as n, MAX(crawled_at) as last FROM pages")
            )
            row = r.fetchone()
        print(f"\nIndex Stats")
        print(f"  Pages in PostgreSQL : {row.n:,}")
        print(f"  Last crawled        : {str(row.last)[:16] if row.last else 'never'}")

    asyncio.run(_run())


DISPATCH = {
    "db":            cmd_db,
    "server":        cmd_server,
    "worker":        cmd_worker,
    "beat":          cmd_beat,
    "worker-health": cmd_worker_health,
    "crawl":         cmd_crawl,
    "search":        cmd_search,
    "factcheck":     cmd_factcheck,
    "shell":         cmd_shell,
    "index":         cmd_index,
    "seeds":         cmd_seeds,
    "index-stats":   cmd_index_stats,
}


def main():
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    handler = DISPATCH.get(args.command)
    if handler is None:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)

    try:
        handler(args)
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
