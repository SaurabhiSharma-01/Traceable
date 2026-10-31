"""
config.py — App settings loaded from backend/.env via pydantic-settings.

Environment variables (set in backend/.env, never committed):
  LLM_PROVIDER        — which LLM backend to use (default: gemini)
  GEMINI_API_KEY      — key for Google Gemini (https://aistudio.google.com/app/apikey)
  GEMINI_MODEL        — model to use (default: gemini-2.5-flash)
  LLM_TEMPERATURE     — generation temperature (default: 0.1)
  LLM_MAX_CONCURRENCY — max parallel requests to the LLM (default: 3)
  LLM_TIMEOUT_SECONDS — timeout per LLM call (default: 60)
  LLM_CACHE_ENABLED   — whether response caching in SQLite is enabled (default: True)
  SQLITE_DB_PATH      — path to SQLite db for caching & storage (default: traceable.sqlite)
  SEARCH_API_KEY      — key for Tavily search (https://app.tavily.com)
  STALE_MONTHS        — months after which a source is considered stale (default: 12)
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_CONCURRENCY: int = 3
    LLM_TIMEOUT_SECONDS: float = 60.0
    LLM_CACHE_ENABLED: bool = True
    SQLITE_DB_PATH: str = "traceable.sqlite"

    SEARCH_API_KEY: str = ""
    STALE_MONTHS: int = 12


settings = Settings()
