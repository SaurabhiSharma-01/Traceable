from __future__ import annotations

from abc import ABC, abstractmethod


class SearchProvider(ABC):
    """Abstract base class for web search providers."""

    @abstractmethod
    async def search(self, query: str, max_results: int) -> list[dict]:
        """
        Search for the given query.

        Returns a list of dicts with keys: url, title, snippet.
        """
        ...
