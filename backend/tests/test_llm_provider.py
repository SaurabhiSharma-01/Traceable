"""
test_llm_provider.py — Unit tests for the LLM provider layer using injected fake client.

Covers:
- valid JSON returns a validated object
- invalid JSON then valid JSON triggers repair retry and succeeds
- invalid JSON twice raises LLMOutputError
- 429 then success triggers backoff and succeeds
- repeated 503 raises LLMUnavailableError
- 401 raises LLMConfigError with no retry
- cache hit returns without calling the client; cache=False bypasses the cache
- failures are not cached
- concurrency never exceeds LLM_MAX_CONCURRENCY
- keys starting with AQ. and AIza are both accepted (no prefix validation)
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, List

import pytest
from pydantic import BaseModel

from app.config import settings
from app.llm.errors import (
    LLMConfigError,
    LLMOutputError,
    LLMUnavailableError,
)
from app.llm.provider import (
    generate_json,
    reset_client,
    set_client,
)

_original_sleep = asyncio.sleep


class SampleItem(BaseModel):
    name: str
    count: int


class FakeResponse:
    def __init__(self, text: str, total_tokens: int = 15):
        self.text = text
        self.total_tokens = total_tokens


class FakeClient:
    def __init__(self, side_effects: List[Any]):
        self.side_effects = list(side_effects)
        self.call_count = 0
        self.prompts: list[str] = []
        self.active_calls = 0
        self.max_active_calls = 0

    async def generate_content(self, contents: str, schema: Any, system: str) -> FakeResponse:
        self.call_count += 1
        self.prompts.append(contents)
        self.active_calls += 1
        self.max_active_calls = max(self.max_active_calls, self.active_calls)

        await _original_sleep(0.01)

        try:
            if not self.side_effects:
                raise RuntimeError("FakeClient exhausted side effects")
            effect = self.side_effects.pop(0)
            if isinstance(effect, Exception):
                raise effect
            return FakeResponse(effect)
        finally:
            self.active_calls -= 1


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Ensure clean isolated configuration for each test."""
    db_file = str(tmp_path / "test_traceable.sqlite")
    monkeypatch.setattr(settings, "SQLITE_DB_PATH", db_file)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini")
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AQ.test_key_sample")
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(settings, "LLM_CACHE_ENABLED", True)
    monkeypatch.setattr(settings, "LLM_MAX_CONCURRENCY", 3)

    # Patch asyncio.sleep to fast-forward backoff loops without recursion
    async def fast_sleep(d=0):
        await _original_sleep(0.001)

    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    reset_client()
    yield
    reset_client()


@pytest.mark.asyncio
async def test_valid_json_returns_validated_object():
    fake = FakeClient([json.dumps({"name": "Scholarship", "count": 10})])
    set_client(fake)

    res = await generate_json("Get details", SampleItem, cache=False)
    assert isinstance(res, SampleItem)
    assert res.name == "Scholarship"
    assert res.count == 10
    assert fake.call_count == 1


@pytest.mark.asyncio
async def test_invalid_json_then_valid_triggers_repair_retry():
    # First attempt returns invalid text, second returns valid JSON
    fake = FakeClient([
        "Malformed string not json",
        json.dumps({"name": "RepairedScholarship", "count": 25}),
    ])
    set_client(fake)

    res = await generate_json("Get details", SampleItem, cache=False)
    assert res.name == "RepairedScholarship"
    assert res.count == 25
    assert fake.call_count == 2
    assert "Your previous output was invalid" in fake.prompts[1]


@pytest.mark.asyncio
async def test_invalid_json_twice_raises_llm_output_error():
    fake = FakeClient([
        "Invalid 1",
        "Invalid 2",
    ])
    set_client(fake)

    with pytest.raises(LLMOutputError) as exc_info:
        await generate_json("Get details", SampleItem, cache=False)

    assert "Validation failed after repair retry" in str(exc_info.value)
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_429_then_success_triggers_backoff_and_succeeds():
    err_429 = Exception("429 Resource Exhausted")
    fake = FakeClient([
        err_429,
        json.dumps({"name": "After429", "count": 3}),
    ])
    set_client(fake)

    res = await generate_json("Get details", SampleItem, cache=False)
    assert res.name == "After429"
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_repeated_503_raises_llm_unavailable_error():
    fake = FakeClient([
        Exception("503 Service Unavailable"),
        Exception("503 Service Unavailable"),
        Exception("503 Service Unavailable"),
    ])
    set_client(fake)

    with pytest.raises(LLMUnavailableError) as exc_info:
        await generate_json("Get details", SampleItem, cache=False)

    assert "Service unavailable after 3 attempts" in str(exc_info.value)
    assert fake.call_count == 3


@pytest.mark.asyncio
async def test_401_raises_llm_config_error_with_no_retry():
    fake = FakeClient([Exception("401 Unauthorized")])
    set_client(fake)

    with pytest.raises(LLMConfigError) as exc_info:
        await generate_json("Get details", SampleItem, cache=False)

    assert "GEMINI_API_KEY missing or rejected" in str(exc_info.value)
    assert fake.call_count == 1  # No retries on 401


@pytest.mark.asyncio
async def test_cache_hit_and_cache_bypass(tmp_path: Path):
    fake = FakeClient([
        json.dumps({"name": "CachedItem", "count": 99}),
        json.dumps({"name": "FreshItem", "count": 100}),
    ])
    set_client(fake)

    # First call: cache miss, calls client
    res1 = await generate_json("Fixed Query", SampleItem, cache=True)
    assert res1.name == "CachedItem"
    assert fake.call_count == 1

    # Second call with same prompt: cache hit, fake client NOT called
    res2 = await generate_json("Fixed Query", SampleItem, cache=True)
    assert res2.name == "CachedItem"
    assert fake.call_count == 1  # unchanged!

    # Third call with cache=False: bypasses cache and calls client
    res3 = await generate_json("Fixed Query", SampleItem, cache=False)
    assert res3.name == "FreshItem"
    assert fake.call_count == 2


@pytest.mark.asyncio
async def test_failures_are_not_cached():
    fake = FakeClient([
        "Invalid Json 1",
        "Invalid Json 2",
        json.dumps({"name": "Recovered", "count": 1}),
    ])
    set_client(fake)

    # First attempt fails
    with pytest.raises(LLMOutputError):
        await generate_json("Same Query", SampleItem, cache=True)
    assert fake.call_count == 2

    # Second call should not read a failed cache entry; it calls client
    res = await generate_json("Same Query", SampleItem, cache=True)
    assert res.name == "Recovered"
    assert fake.call_count == 3


@pytest.mark.asyncio
async def test_concurrency_never_exceeds_max_concurrency(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "LLM_MAX_CONCURRENCY", 2)
    reset_client()  # Re-init semaphore with max concurrency 2
    fake = FakeClient([
        json.dumps({"name": f"Item{i}", "count": i})
        for i in range(6)
    ])
    set_client(fake)

    tasks = [
        generate_json(f"Query {i}", SampleItem, cache=False)
        for i in range(6)
    ]
    results = await asyncio.gather(*tasks)

    assert len(results) == 6
    assert fake.max_active_calls <= 2


@pytest.mark.asyncio
async def test_keys_with_aq_and_aiza_accepted(monkeypatch: pytest.MonkeyPatch):
    # Verify AQ. key is accepted without error
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AQ.random_key_12345")
    fake = FakeClient([json.dumps({"name": "AQ_Key", "count": 1})])
    set_client(fake)
    res_aq = await generate_json("Query AQ", SampleItem, cache=False)
    assert res_aq.name == "AQ_Key"

    # Verify AIza key is accepted without error
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AIzaSyD_sample_key_67890")
    fake2 = FakeClient([json.dumps({"name": "AIza_Key", "count": 2})])
    set_client(fake2)
    res_aiza = await generate_json("Query AIza", SampleItem, cache=False)
    assert res_aiza.name == "AIza_Key"
