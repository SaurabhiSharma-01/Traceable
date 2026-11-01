#!/usr/bin/env python3
"""
benchmark_models.py — Benchmark available Gemini models for structured-output latency.

Discovers real models from the API (no hardcoded names).
For each candidate, tries thinking settings in order:
  1. thinking_level = LOW
  2. thinking_budget = 0
  3. no thinking config

Usage:
    cd backend
    python scripts/benchmark_models.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Ensure backend root is on sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path, override=True)

# Import after env load so settings picks up .env values
from app.config import settings  # noqa: E402


# ---------------------------------------------------------------------------
# Tiny Pydantic schema for the benchmark call
# ---------------------------------------------------------------------------
from pydantic import BaseModel  # noqa: E402


class Hello(BaseModel):
    message: str
    language: str


PROMPT = "Say hello in Hindi. Return JSON with fields: message (the Hindi greeting), language (always 'Hindi')."
SYSTEM = "You are a helpful assistant. Return only valid JSON."
TIMEOUT_SECS = 25


# ---------------------------------------------------------------------------
# Thinking-setting descriptors
# ---------------------------------------------------------------------------
THINKING_SETTINGS = [
    ("level:low", "thinking_level=LOW"),
    ("budget:0", "thinking_budget=0"),
    ("none", "no thinking config"),
]


def _build_cfg(types_mod: Any, setting_key: str, schema: type) -> Any:
    """Build a GenerateContentConfig for the given setting key."""
    base = {
        "response_mime_type": "application/json",
        "response_schema": schema,
        "temperature": 0.1,
    }
    if setting_key == "none":
        return types_mod.GenerateContentConfig(**base)
    if setting_key == "level:low":
        try:
            level = types_mod.ThinkingLevel.LOW
            base["thinking_config"] = types_mod.ThinkingConfig(thinking_level=level)
            return types_mod.GenerateContentConfig(**base)
        except Exception:
            return None
    if setting_key == "budget:0":
        try:
            base["thinking_config"] = types_mod.ThinkingConfig(thinking_budget=0)
            return types_mod.GenerateContentConfig(**base)
        except Exception:
            return None
    return None


def _try_call(client: Any, model_name: str, cfg: Any) -> tuple[str, float]:
    """Synchronous single call; returns (outcome, seconds). outcome: ok/400/503/timeout/error."""
    from google.genai import errors as genai_errors  # type: ignore

    t0 = time.perf_counter()
    try:
        resp = client.models.generate_content(
            model=model_name,
            contents=PROMPT,
            config=cfg,
        )
        elapsed = time.perf_counter() - t0
        _ = resp.text  # access to ensure response is complete
        return "ok", round(elapsed, 2)
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        msg = str(exc).lower()
        if "400" in msg or "invalid argument" in msg or "bad request" in msg:
            return "400", round(elapsed, 2)
        if "503" in msg or "overloaded" in msg or "high demand" in msg or "unavailable" in msg:
            return "503", round(elapsed, 2)
        if "timeout" in msg or "deadline" in msg or "timed out" in msg:
            return "timeout", round(elapsed, 2)
        # Include short error tag for other failures
        tag = type(exc).__name__[:12]
        return tag, round(elapsed, 2)


def run_benchmark() -> None:
    api_key = settings.GEMINI_API_KEY
    if not api_key or not api_key.strip():
        print("ERROR: GEMINI_API_KEY not set in backend/.env")
        sys.exit(1)

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key.strip())

    # ------------------------------------------------------------------
    # 1. List all models that support generateContent
    # ------------------------------------------------------------------
    print("Discovering models available to your key...\n")
    all_models: list[str] = []
    try:
        pager = client.models.list()
        for m in pager:
            name: str = getattr(m, "name", "") or ""
            # Strip "models/" prefix
            if name.startswith("models/"):
                name = name[len("models/"):]
            methods = (
                getattr(m, "supported_generation_methods", None)
                or getattr(m, "supported_actions", None)
                or []
            )
            if "generateContent" in (methods or []):
                all_models.append(name)
    except Exception as exc:
        print(f"WARNING: Could not list models ({exc}). Falling back to current GEMINI_MODEL only.")
        all_models = [settings.GEMINI_MODEL]

    print(f"Models supporting generateContent ({len(all_models)} total):")
    for m in sorted(all_models):
        print(f"  {m}")
    print()

    # ------------------------------------------------------------------
    # 2. Pick up to 4 candidates:
    #    current GEMINI_MODEL + any flash-lite + any other flash variants
    # ------------------------------------------------------------------
    current = settings.GEMINI_MODEL
    candidates: list[str] = []

    # Always include current model
    if current in all_models:
        candidates.append(current)
    elif all_models:
        candidates.append(all_models[0])  # fallback

    # Prefer flash-lite variants
    for m in all_models:
        if "flash-lite" in m and m not in candidates:
            candidates.append(m)
            if len(candidates) == 4:
                break

    # Then other flash variants
    for m in all_models:
        if "flash" in m and m not in candidates:
            candidates.append(m)
            if len(candidates) == 4:
                break

    # Fill remaining slots with anything else
    for m in all_models:
        if m not in candidates:
            candidates.append(m)
            if len(candidates) == 4:
                break

    print(f"Selected candidates for benchmark: {candidates}\n")

    # ------------------------------------------------------------------
    # 3. Benchmark each candidate × each thinking setting
    # ------------------------------------------------------------------
    rows: list[tuple[str, str, str, float]] = []  # (model, setting, result, secs)

    for model_name in candidates:
        prev_ok = False
        for setting_key, setting_label in THINKING_SETTINGS:
            if prev_ok:
                # Already found a working setting; skip remaining for this model
                rows.append((model_name, setting_label, "skipped", 0.0))
                continue

            cfg = _build_cfg(types, setting_key, Hello)
            if cfg is None:
                rows.append((model_name, setting_label, "cfg_err", 0.0))
                continue

            print(f"  Testing {model_name!r} with {setting_label} ...", end=" ", flush=True)
            try:
                outcome, secs = _run_with_timeout(client, model_name, cfg, TIMEOUT_SECS)
            except Exception as exc:
                outcome, secs = f"err:{type(exc).__name__[:8]}", 0.0

            print(f"{outcome} ({secs}s)")
            rows.append((model_name, setting_label, outcome, secs))

            if outcome == "ok":
                prev_ok = True  # Stop trying more settings for this model

        print()

    # ------------------------------------------------------------------
    # 4. Print table
    # ------------------------------------------------------------------
    print("\n" + "=" * 78)
    print(f"{'MODEL':<35} {'SETTING':<24} {'RESULT':<10} {'SECONDS':>7}")
    print("-" * 78)
    for model_name, setting_label, result, secs in rows:
        secs_str = f"{secs:.2f}s" if secs > 0 else "-"
        print(f"{model_name:<35} {setting_label:<24} {result:<10} {secs_str:>7}")
    print("=" * 78)

    # ------------------------------------------------------------------
    # 5. Recommend fastest successful setting
    # ------------------------------------------------------------------
    ok_rows = [(m, s, r, t) for m, s, r, t in rows if r == "ok"]
    if ok_rows:
        best = min(ok_rows, key=lambda x: x[3])
        best_model, best_setting_label, _, best_secs = best
        # Map setting_label back to setting_key
        label_to_key = {lbl: key for key, lbl in THINKING_SETTINGS}
        best_key = label_to_key.get(best_setting_label, "none")

        print(f"\n✓ Recommendation: model={best_model!r}, setting={best_setting_label!r}, latency={best_secs:.2f}s")
        print(f"\nSet these in backend/.env:")
        print(f"  GEMINI_MODEL={best_model}")
        if best_key.startswith("level:"):
            level = best_key.split(":")[1]
            print(f"  LLM_THINKING_LEVEL={level}")
        elif best_key == "budget:0":
            print(f"  LLM_THINKING_LEVEL=budget:0")
        else:
            print(f"  LLM_THINKING_LEVEL=none")
    else:
        print("\n✗ No model succeeded within the timeout. Check your API key and quota.")


def _run_with_timeout(client: Any, model_name: str, cfg: Any, timeout: float) -> tuple[str, float]:
    """Run a sync call in a thread with a wall-clock timeout."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_try_call, client, model_name, cfg)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return "timeout", timeout


if __name__ == "__main__":
    run_benchmark()

