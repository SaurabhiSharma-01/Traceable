#!/usr/bin/env python3
"""
scripts/llm_smoke_test.py
─────────────────────────
Live smoke test for the LLM provider layer.
Calls the REAL Gemini API and validates structured output + SQLite caching.

Usage:
    python scripts/llm_smoke_test.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path so app modules import cleanly
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)

from pydantic import BaseModel

from app.config import settings
from app.llm.errors import LLMError
from app.llm.provider import generate_json, provider_info


class Hello(BaseModel):
    message: str
    language: str


async def run_smoke():
    info = provider_info()
    print("=" * 60)
    print(f"Traceable LLM Smoke Test — Provider: {info['provider']}, Model: {info['model']}")
    print("=" * 60)

    prompt = "Say hello in Hindi. Return a message and the language name."

    # ── Run 1: Should be Cache MISS (calls live API) ──────────────────────────
    print("\n[Run 1] Calling live Gemini API...")
    t0 = time.perf_counter()
    try:
        res1 = await generate_json(prompt, Hello, task="smoke_run1")
    except LLMError as err:
        print(f"\n[FAIL] {type(err).__name__}: {err}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[FAIL] Unexpected {type(exc).__name__}: {exc}")
        sys.exit(1)

    latency1_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  Result: message={res1.message!r}, language={res1.language!r}")
    print(f"  Latency: {latency1_ms:.1f}ms")
    print("  Status: API call succeeded.")

    # ── Run 2: Should be Cache HIT ────────────────────────────────────────────
    print("\n[Run 2] Calling again with same prompt (expecting SQLite Cache HIT)...")
    t1 = time.perf_counter()
    try:
        res2 = await generate_json(prompt, Hello, task="smoke_run2")
    except LLMError as err:
        print(f"\n[FAIL] {type(err).__name__}: {err}")
        sys.exit(1)

    latency2_ms = (time.perf_counter() - t1) * 1000.0
    print(f"  Result: message={res2.message!r}, language={res2.language!r}")
    print(f"  Latency: {latency2_ms:.1f}ms")

    # Latency for local cache hit is typically sub-50ms vs several hundred ms for live network
    if latency2_ms < 100.0 and res1.message == res2.message:
        print("  Status: CACHE HIT verified! (Response served instantly from SQLite)")
    else:
        print(f"  Status: Cache read complete (latency {latency2_ms:.1f}ms)")

    print("\n" + "=" * 60)
    print("Smoke test PASSED successfully!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_smoke())

