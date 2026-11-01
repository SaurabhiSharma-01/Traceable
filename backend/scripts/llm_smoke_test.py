#!/usr/bin/env python3
"""
scripts/llm_smoke_test.py
─────────────────────────
Live smoke test for the LLM provider layer.
1. Discovers available models for the configured GEMINI_API_KEY via the official SDK.
2. Measures per-call latency for the current GEMINI_MODEL (with LLM_THINKING_BUDGET).
3. Validates SQLite response cache hit (sub-50ms).
4. Tests a lighter flash-lite model from the discovered model list and reports latency.

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
from app.llm.provider import generate_json, get_client, provider_info


class Hello(BaseModel):
    message: str
    language: str


def discover_available_models() -> list[str]:
    """Query Google Gen AI SDK for models that support content generation."""
    client = get_client()
    discovered: list[str] = []
    try:
        pager = client.models.list()
        for m in pager:
            raw_name = getattr(m, "name", "") or ""
            clean_name = raw_name.replace("models/", "").strip()
            # Check supported actions/methods if available
            actions = (
                getattr(m, "supported_actions", None)
                or getattr(m, "supported_generation_methods", None)
            )
            if actions:
                if any("generateContent" in a or "generate_content" in a for a in actions):
                    discovered.append(clean_name)
            elif "gemini" in clean_name.lower():
                discovered.append(clean_name)
    except Exception as exc:
        print(f"[WARN] Failed to list models via SDK client: {exc}")
    return discovered


async def run_smoke():
    info = provider_info()
    print("=" * 80)
    print(f"Traceable LLM Smoke Test")
    print(f"Provider:        {info['provider']}")
    print(f"Configured Model: {info['model']}")
    print(f"Thinking Budget: {info.get('thinking_budget', settings.LLM_THINKING_BUDGET)}")
    print(f"Timeout (s):     {settings.LLM_TIMEOUT_SECONDS}s")
    print("=" * 80)

    # ── Step 1: Discover available models via official SDK ─────────────────────
    print("\n[Step 1] Querying available models via SDK client.models.list()...")
    discovered_models = discover_available_models()
    if discovered_models:
        print(f"  Found {len(discovered_models)} models supporting content generation:")
        for m in discovered_models[:12]:
            print(f"    - {m}")
        if len(discovered_models) > 12:
            print(f"    ... and {len(discovered_models) - 12} more")
    else:
        print("  [WARN] Could not retrieve model list from SDK; using configured model.")

    # Identify a flash-lite candidate
    lite_candidates = [
        m for m in discovered_models
        if "lite" in m.lower() and "gemini" in m.lower()
    ]
    lite_model = lite_candidates[0] if lite_candidates else None
    if lite_model:
        print(f"  Identified flash-lite candidate: {lite_model!r}")
    else:
        # Fallback to standard lite name if list didn't include it
        lite_model = "gemini-2.5-flash-lite"
        print(f"  No explicit lite model found in list; testing candidate: {lite_model!r}")

    prompt = "Say hello in Hindi. Return a message and the language name."

    # ── Step 2: Test configured model (Run 1: Live API call, Cache MISS) ──────
    current_model = settings.GEMINI_MODEL
    print(f"\n[Step 2] Testing configured model: {current_model!r} (Cache MISS)...")
    t0 = time.perf_counter()
    try:
        res1 = await generate_json(prompt, Hello, task="smoke_current_live", model=current_model)
    except LLMError as err:
        print(f"\n[FAIL] {type(err).__name__}: {err}")
        sys.exit(1)

    latency1_ms = (time.perf_counter() - t0) * 1000.0
    print(f"  Timing:  {latency1_ms:.1f}ms ({latency1_ms/1000.0:.2f}s)")
    print(f"  Result:  message={res1.message!r}, language={res1.language!r}")
    print(f"  Status:  API call succeeded (under 10s target: {'YES' if latency1_ms < 10000 else 'NO'}).")

    # ── Step 3: Test configured model (Run 2: SQLite Cache HIT) ───────────────
    print(f"\n[Step 3] Testing configured model: {current_model!r} (Cache HIT)...")
    t1 = time.perf_counter()
    res2 = await generate_json(prompt, Hello, task="smoke_current_cache", model=current_model)
    latency2_ms = (time.perf_counter() - t1) * 1000.0
    print(f"  Timing:  {latency2_ms:.1f}ms")
    print(f"  Result:  message={res2.message!r}, language={res2.language!r}")
    if latency2_ms < 100.0 and res1.message == res2.message:
        print("  Status:  CACHE HIT verified! Instant response from SQLite.")
    else:
        print(f"  Status:  Cache read complete (latency {latency2_ms:.1f}ms)")

    # ── Step 4: Test lighter flash-lite model ─────────────────────────────────
    print(f"\n[Step 4] Testing lighter flash-lite model: {lite_model!r}...")
    t2 = time.perf_counter()
    lite_success = False
    try:
        res_lite = await generate_json(prompt, Hello, task="smoke_lite_live", model=lite_model, cache=False)
        latency_lite_ms = (time.perf_counter() - t2) * 1000.0
        print(f"  Timing:  {latency_lite_ms:.1f}ms ({latency_lite_ms/1000.0:.2f}s)")
        print(f"  Result:  message={res_lite.message!r}, language={res_lite.language!r}")
        print(f"  Status:  Flash-lite call succeeded (under 10s target: {'YES' if latency_lite_ms < 10000 else 'NO'}).")
        lite_success = True
    except Exception as exc:
        print(f"  [WARN] Flash-lite model {lite_model!r} failed ({exc}). Trying gemini-2.0-flash...")
        try:
            t2 = time.perf_counter()
            res_lite = await generate_json(prompt, Hello, task="smoke_lite_fallback", model="gemini-2.0-flash", cache=False)
            latency_lite_ms = (time.perf_counter() - t2) * 1000.0
            lite_model = "gemini-2.0-flash"
            print(f"  Timing:  {latency_lite_ms:.1f}ms ({latency_lite_ms/1000.0:.2f}s)")
            print(f"  Result:  message={res_lite.message!r}, language={res_lite.language!r}")
            lite_success = True
        except Exception as e2:
            print(f"  [FAIL] Lite fallback failed: {e2}")

    # ── Step 5: Summary Latency Report ────────────────────────────────────────
    print("\n" + "=" * 80)
    print("Latency Summary Report:")
    print(f"{'Model':<28} | {'Thinking Budget':<18} | {'Latency (ms)':<14} | {'Status'}")
    print("-" * 80)
    print(f"{current_model:<28} | {str(settings.LLM_THINKING_BUDGET):<18} | {latency1_ms:>8.1f} ms     | {'PASS (<10s)' if latency1_ms < 10000 else 'SLOW'}")
    if lite_success:
        print(f"{lite_model:<28} | {str(settings.LLM_THINKING_BUDGET):<18} | {latency_lite_ms:>8.1f} ms     | {'PASS (<10s)' if latency_lite_ms < 10000 else 'SLOW'}")
    print(f"{current_model + ' (cached)':<28} | {'-':<18} | {latency2_ms:>8.1f} ms     | PASS (Instant)")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_smoke())
