"""
Configuration — loads from environment variables
All search API keys removed. Zero external search dependency.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    # OpenRouter (LLM — free tier works)
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Free LLM models (no cost on OpenRouter free tier)
    fast_model: str = "google/gemini-2.0-flash-exp:free"
    deep_model: str = "deepseek/deepseek-chat:free"

    # Databases
    # Accepts DATABASE_URL (Render/Heroku/Neon convention) OR postgres_url.
    # DATABASE_URL is checked first; postgres_url is the fallback field name.
    postgres_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ultrasearch",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = "redis://localhost:6379"

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
    search_bm25_top_k: int = 50          # over-fetch from PG FTS
    search_final_top_k: int = 20         # results after BM25
    search_min_score: float = 0.0

    # Research
    research_max_sources: int = 15
    research_max_depth: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow both DATABASE_URL and postgres_url to populate the field
        populate_by_name = True


settings = Settings()
