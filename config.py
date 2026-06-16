"""
Configuration — loads from environment variables
All search API keys removed. Zero external search dependency.
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # OpenRouter (LLM + Embeddings — free tier works)
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Free LLM models (no cost on OpenRouter free tier)
    fast_model: str = "google/gemini-2.0-flash-exp:free"
    deep_model: str = "deepseek/deepseek-chat:free"

    # Free embedding model — NVIDIA Nemotron, $0/M tokens
    # Outputs 1024-dim vectors
    embedding_model: str = "nvidia/llama-nemotron-embed-vl-1b-v2:free"
    embedding_dim: int = 1024

    # Databases
    postgres_url: str = "postgresql://postgres:postgres@localhost:5432/ultrasearch"
    redis_url: str = "redis://localhost:6379"

    # Vector DB (Qdrant)
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "pages"

    # Crawler settings
    crawler_concurrency: int = 8
    crawler_delay_ms: int = 300
    crawler_max_depth: int = 4
    crawler_user_agent: str = "UltraSearchBot/1.0 (+https://ultrasearch.app/bot)"
    crawler_max_pages_per_job: int = 500

    # Indexer
    indexer_chunk_size: int = 400        # words per chunk
    indexer_chunk_overlap: int = 50      # word overlap between chunks
    indexer_batch_size: int = 32         # embed N chunks per API call

    # Search
    search_vector_top_k: int = 50        # over-fetch from Qdrant
    search_bm25_top_k: int = 50          # over-fetch from PG FTS
    search_final_top_k: int = 20         # results after RRF fusion
    search_min_score: float = 0.0        # RRF scores are always > 0

    # Research
    research_max_sources: int = 15
    research_max_depth: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
