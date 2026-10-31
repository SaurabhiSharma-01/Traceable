from __future__ import annotations

import asyncio
import hashlib
from typing import Any


class LLMCache:
    """Thread-safe in-memory cache for LLM completions."""

    def __init__(self) -> None:
        self._store: dict[str, dict] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def make_key(prompt: str, schema_name: str) -> str:
        raw = (prompt + schema_name).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()

    async def get(self, key: str) -> dict | None:
        async with self._lock:
            return self._store.get(key)

    async def set(self, key: str, value: dict) -> None:
        async with self._lock:
            self._store[key] = value


# Module-level singleton
cache = LLMCache()
