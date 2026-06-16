# Ultra Search Engine

AI-powered search backend with multi-agent research, web crawling, vector search, and fact-checking.

---

## Architecture

```
POST /search      → Aggregator → Extractor → Summarizer → JSON
POST /research    → Planner → Search → Verifier → Writer → JSON Report
POST /crawl       → Spider → Queue → Embedder → Qdrant
GET  /health      → 200 OK
```

## Stack

| Layer        | Technology                        |
|--------------|-----------------------------------|
| API          | FastAPI + Uvicorn                 |
| Search       | Brave, Tavily, Serper             |
| LLM          | OpenRouter (GPT-4.1-mini / GPT-4o)|
| Vector DB    | Qdrant                            |
| Database     | PostgreSQL (SQLAlchemy async)      |
| Task Queue   | Celery + Redis                    |
| Crawling     | httpx + BeautifulSoup (async BFS) |

---

## Quickstart

### 1. Copy env file and add keys

```bash
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start all services with Docker

```bash
docker compose up -d
```

This starts: API server, PostgreSQL, Redis, Qdrant, and three Celery workers (crawler, embedder, researcher) plus Flower for monitoring.

### 3. Test it

```bash
# Search
curl -X POST http://localhost:8000/search \
  -H "Content-Type: application/json" \
  -d '{"query": "latest AI models 2025", "summarize": true}'

# Deep research
curl -X POST http://localhost:8000/research \
  -H "Content-Type: application/json" \
  -d '{"query": "impact of LLMs on software engineering", "depth": 2}'

# Poll job result
curl http://localhost:8000/research/{job_id}

# Crawl a site
curl -X POST http://localhost:8000/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "max_depth": 2}'
```

---

## File Structure

```
backend/
├── app.py                  # FastAPI entry point
├── config.py               # Settings (env-based)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
│
├── api/
│   ├── search.py           # POST /search
│   ├── research.py         # POST /research
│   └── crawl.py            # POST /crawl
│
├── search/
│   ├── brave.py            # Brave Search provider
│   ├── tavily.py           # Tavily provider
│   ├── serper.py           # Serper (Google) provider
│   └── aggregator.py       # Fan-out + merge + dedupe
│
├── extractor/
│   ├── fetcher.py          # Async HTTP downloader
│   ├── parser.py           # HTML → structured content
│   ├── cleaner.py          # Normalize, strip ads, truncate
│   └── dedupe.py           # URL + SimHash deduplication
│
├── llm/
│   ├── router.py           # OpenRouter base client
│   ├── planner.py          # Research Planner agent
│   ├── summarizer.py       # Search result summarizer
│   ├── verifier.py         # Fact verification agent
│   └── writer.py           # Report writer agent
│
├── crawler/
│   ├── spider.py           # Async BFS spider
│   ├── scheduler.py        # Priority queue scheduler
│   ├── robots.py           # robots.txt cache
│   └── extractor.py        # (see extractor/ module)
│
├── vector/
│   ├── store.py            # Qdrant client wrapper
│   └── embedder.py         # Embedding + chunking
│
├── factcheck/
│   └── checker.py          # End-to-end fact check
│
├── database/
│   └── models.py           # SQLAlchemy async models
│
└── workers/
    └── tasks.py            # Celery tasks
```

---

## Workers

Run separately (or via Docker Compose):

```bash
# Crawler worker
celery -A workers.tasks worker -Q crawl -c 4

# Embedding worker
celery -A workers.tasks worker -Q embed -c 2

# Research worker
celery -A workers.tasks worker -Q research -c 2

# Monitor
celery -A workers.tasks flower
# → http://localhost:5555
```

---

## Adding a Search Provider

1. Create `search/myprovider.py` with a class that has `async def search(query, num_results) -> List[Dict]`
2. Register it in `search/aggregator.py` `_get_provider()`
3. Pass `"myprovider"` in the `sources` array of your `/search` request
