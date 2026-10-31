"""
search.py — Search provider layer with Tavily integration, caching, and retries.

Never logs secrets or API keys.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import aiosqlite
import httpx
from pydantic import BaseModel

from ..config import settings
from .errors import SearchConfigError, SearchUnavailableError

logger = logging.getLogger("traceable.search")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class SearchResult(BaseModel):
    """Normalized search candidate result."""
    url: str
    title: str
    snippet: Optional[str] = None
    content: Optional[str] = None          # full page text if provider returns it
    published_date: Optional[str] = None   # if provider returns one
    score: Optional[float] = None


class SearchProvider(ABC):
    """Abstract search provider interface."""

    @abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        use_cache: bool = True,
    ) -> list[SearchResult]:
        pass


_initialized_search_dbs: set[str] = set()
_cache_init_lock = asyncio.Lock()


async def _init_search_cache(db_path: str) -> None:
    """Ensure search_cache table exists in SQLite database."""
    abs_path = str(Path(db_path).resolve())
    if abs_path in _initialized_search_dbs:
        return
    async with _cache_init_lock:
        if abs_path in _initialized_search_dbs:
            return
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(abs_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS search_cache (
                    key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.commit()
        _initialized_search_dbs.add(abs_path)


def _compute_search_cache_key(provider: str, query: str, max_results: int, raw_content: bool) -> str:
    raw = f"{provider}:{query.strip().lower()}:{max_results}:{raw_content}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class TavilySearchProvider(SearchProvider):
    """Tavily search implementation using direct HTTPS with structured fallback & retries."""

    TAVILY_API_URL = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: Optional[str] = None,
        http_client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self._api_key = api_key if api_key is not None else settings.SEARCH_API_KEY
        self._client = http_client

    async def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        use_cache: bool = True,
    ) -> list[SearchResult]:
        api_key = self._api_key
        if not api_key or not api_key.strip():
            raise SearchConfigError(
                "SEARCH_API_KEY missing; add it to backend/.env or add URLs manually"
            )

        db_path = settings.SQLITE_DB_PATH
        cache_key = _compute_search_cache_key("tavily", query, max_results, True)

        # 1. Check Cache
        if use_cache:
            await _init_search_cache(db_path)
            try:
                async with aiosqlite.connect(db_path) as db:
                    async with db.execute(
                        "SELECT response_json, created_at FROM search_cache WHERE key = ?",
                        (cache_key,),
                    ) as cursor:
                        row = await cursor.fetchone()
                        if row:
                            data_json, created_at_str = row
                            created_at = datetime.fromisoformat(created_at_str)
                            now = datetime.now(timezone.utc)
                            ttl = timedelta(hours=settings.SEARCH_CACHE_TTL_HOURS)
                            if now - created_at < ttl:
                                logger.info(
                                    "[Search] query=%r depth=advanced cache=HIT results_from_cache",
                                    query[:40],
                                )
                                items = json.loads(data_json)
                                return [SearchResult.model_validate(it) for it in items]
            except Exception as e:
                logger.warning("[Search] Cache read error: %s (continuing with live search)", e)

        # 2. Live API Call with Retry Loop
        payload = {
            "api_key": api_key.strip(),
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_raw_content": True,
        }

        last_error: Optional[Exception] = None
        data: Optional[dict[str, Any]] = None

        for attempt in range(1, 4):
            try:
                # Use provided client or temporary client
                if self._client:
                    resp = await self._client.post(
                        self.TAVILY_API_URL,
                        json=payload,
                        timeout=15.0,
                    )
                else:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        resp = await client.post(
                            self.TAVILY_API_URL,
                            json=payload,
                        )

                # Auth errors — no retry
                if resp.status_code in (401, 403):
                    raise SearchConfigError(
                        f"Tavily API key rejected (status {resp.status_code}); check backend/.env"
                    )

                # Rate limit / Server errors — retry with exponential backoff
                if resp.status_code in (429, 500, 502, 503, 504):
                    retry_after_hdr = resp.headers.get("Retry-After")
                    delay = None
                    if retry_after_hdr:
                        try:
                            delay = float(retry_after_hdr)
                        except (ValueError, TypeError):
                            pass
                    if delay is None:
                        delay = (2 ** (attempt - 1)) + random.uniform(0.1, 0.4)

                    if attempt < 3:
                        logger.warning(
                            "[Search] Tavily transient status %d on attempt %d/3. Backing off %.2fs...",
                            resp.status_code,
                            attempt,
                            delay,
                        )
                        await asyncio.sleep(delay)
                        continue
                    else:
                        raise SearchUnavailableError(
                            f"Tavily service unavailable after {attempt} attempts: HTTP {resp.status_code}"
                        )

                resp.raise_for_status()
                data = resp.json()
                break

            except SearchConfigError:
                raise
            except SearchUnavailableError:
                raise
            except httpx.TimeoutException as te:
                last_error = te
                if attempt < 3:
                    delay = (2 ** (attempt - 1)) + 0.2
                    logger.warning(
                        "[Search] Tavily timeout on attempt %d/3. Backing off %.2fs...",
                        attempt,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    continue
                else:
                    raise SearchUnavailableError(
                        f"Tavily search timed out after {attempt} attempts"
                    ) from te
            except httpx.HTTPError as he:
                last_error = he
                if attempt < 3:
                    await asyncio.sleep(1.0)
                    continue
                else:
                    raise SearchUnavailableError(
                        f"Tavily search network failure after {attempt} attempts: {he}"
                    ) from he

        if data is None:
            raise SearchUnavailableError(f"Search failed: {last_error}")

        # Parse normalized results
        results: list[SearchResult] = []
        raw_items = data.get("results", [])
        for item in raw_items:
            url = item.get("url")
            if not url:
                continue
            title = item.get("title") or url
            snippet = item.get("content")
            raw_content = item.get("raw_content")
            score = item.get("score")
            pub_date = item.get("published_date")

            results.append(
                SearchResult(
                    url=url,
                    title=title,
                    snippet=snippet,
                    content=raw_content if raw_content else None,
                    published_date=str(pub_date) if pub_date else None,
                    score=float(score) if score is not None else None,
                )
            )

        logger.info(
            "[Search] query=%r depth=advanced cache=MISS results=%d",
            query[:40],
            len(results),
        )

        # 3. Write Cache
        if use_cache:
            try:
                now_iso = datetime.now(timezone.utc).isoformat()
                serialized = json.dumps([r.model_dump() for r in results])
                async with aiosqlite.connect(db_path) as db:
                    await db.execute(
                        """
                        INSERT OR REPLACE INTO search_cache (key, response_json, created_at)
                        VALUES (?, ?, ?)
                        """,
                        (cache_key, serialized, now_iso),
                    )
                    await db.commit()
            except Exception as e:
                logger.warning("[Search] Cache write error: %s", e)

        return results


# Global provider instance
_default_provider: Optional[SearchProvider] = None


def get_search_provider(http_client: Optional[httpx.AsyncClient] = None) -> SearchProvider:
    """Return default search provider (Tavily)."""
    global _default_provider
    if http_client is not None:
        return TavilySearchProvider(http_client=http_client)
    if _default_provider is None:
        _default_provider = TavilySearchProvider()
    return _default_provider


def set_search_provider(provider: Optional[SearchProvider]) -> None:
    """Inject search provider for testing."""
    global _default_provider
    _default_provider = provider


async def search(
    query: str,
    max_results: int = 5,
    *,
    use_cache: bool = True,
    http_client: Optional[httpx.AsyncClient] = None,
) -> list[SearchResult]:
    """Execute search query using default configured provider."""
    provider = get_search_provider(http_client=http_client)
    return await provider.search(query=query, max_results=max_results, use_cache=use_cache)
