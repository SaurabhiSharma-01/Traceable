from __future__ import annotations

import logging

import httpx

from ..config import settings
from .provider import SearchProvider

logger = logging.getLogger(__name__)

_TAVILY_URL = "https://api.tavily.com/search"


class TavilySearchProvider(SearchProvider):
    """Tavily-backed search provider."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.SEARCH_API_KEY

    async def search(self, query: str, max_results: int = 10) -> list[dict]:
        payload = {
            "api_key": self._api_key,
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(_TAVILY_URL, json=payload)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                raise RuntimeError(
                    f"Tavily search failed with status {exc.response.status_code}: {exc.response.text}"
                ) from exc
            except Exception as exc:
                raise RuntimeError(f"Tavily search error: {exc}") from exc

        results = data.get("results", [])
        normalized: list[dict] = []
        for item in results:
            normalized.append(
                {
                    "url": item.get("url", ""),
                    "title": item.get("title", ""),
                    "snippet": item.get("content", ""),
                }
            )
        return normalized
