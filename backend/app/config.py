"""
config.py — App settings loaded from backend/.env via pydantic-settings.

Environment variables (set in backend/.env, never committed):
  LLM_PROVIDER        — which LLM backend to use (default: gemini)
  GEMINI_API_KEY      — key for Google Gemini (https://aistudio.google.com/app/apikey)
  GEMINI_MODEL        — model to use (default: gemini-2.5-flash)
  LLM_TEMPERATURE     — generation temperature (default: 0.1)
  LLM_MAX_CONCURRENCY — max parallel requests to the LLM (default: 3)
  LLM_TIMEOUT_SECONDS — per-call timeout; timeouts retried once (default: 45)
  LLM_THINKING_LEVEL  — thinking cascade start: "low" | "budget:0" | "none" (default: low)
                        "low"      -> try ThinkingLevel.LOW first, then budget:0, then none
                        "budget:0" -> try thinking_budget=0 first, then none
                        "none"     -> omit thinking_config entirely
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
    LLM_TIMEOUT_SECONDS: float = 45.0
    LLM_THINKING_LEVEL: str = "low"
    LLM_CACHE_ENABLED: bool = True
    SQLITE_DB_PATH: str = "traceable.sqlite"

    SEARCH_API_KEY: str = ""
    STALE_MONTHS: int = 12
    SEARCH_CACHE_TTL_HOURS: int = 24
    PAGE_CACHE_TTL_HOURS: int = 24


settings = Settings()
