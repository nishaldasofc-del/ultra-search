"""
Configuration — loads from environment variables
All search API keys removed. Zero external search dependency.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from pydantic.aliases import AliasChoices
from typing import Optional


class Settings(BaseSettings):
    # OpenRouter (LLM — free tier works)
    openrouter_api_key: Optional[str] = None
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Free LLM models (no cost on OpenRouter free tier)
    fast_model: str = "google/gemini-2.0-flash-exp:free"
    deep_model: str = "deepseek/deepseek-chat:free"

    # Databases
    # Accepts POSTGRES_URL (our convention, set in Render env vars and .env)
    # or DATABASE_URL (Neon/Heroku convention) — whichever is present.
    postgres_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/ultrasearch",
        validation_alias=AliasChoices("POSTGRES_URL", "DATABASE_URL", "postgres_url"),
    )
    redis_url: str = "redis://localhost:6379"

    # Crawler settings
    crawler_concurrency: int = 8
    crawler_delay_ms: int = 300
    crawler_max_depth: int = 4
    crawler_user_agent: str = "UltraSearchBot/1.0 (+https://ultrasearch.app/bot)"
    crawler_max_pages_per_job: int = 500

    # Indexer
    indexer_chunk_size: int = 400
    indexer_chunk_overlap: int = 50
    indexer_batch_size: int = 32

    # Search
    search_bm25_top_k: int = 50
    search_final_top_k: int = 20
    search_min_score: float = 0.0

    # Research
    research_max_sources: int = 15
    research_max_depth: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        populate_by_name = True


settings = Settings()
