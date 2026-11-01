#!/usr/bin/env python3
"""
scripts/understand_demo.py
──────────────────────────
Developer CLI demo script for Phase 4 query understanding:
Calls understand() against real Gemini and prints entity, entity type, intent,
ambiguity note, and a table of generated verification topics.
Run twice to observe SQLite cache hits.

Usage:
    python scripts/understand_demo.py "What should I verify before applying for the PM YASASVI scholarship?"
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
from pathlib import Path

backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)

from app.pipeline.query_understanding import understand


async def run_demo(question: str):
    print("=" * 95)
    print("Traceable Query Understanding Demo (Module A)")
    print(f"Question: {question!r}")
    print("=" * 95)

    # First run (may be live API call or cache)
    print("\n[Run 1] Executing understand()...")
    t0 = time.perf_counter()
    res1 = await understand(question)
    elapsed1 = (time.perf_counter() - t0) * 1000.0

    print(f"Elapsed: {elapsed1:.1f}ms")
    print(f"Entity:                {res1.entity}")
    print(f"Entity Type:           {res1.entity_type}")
    print(f"Intent:                {res1.intent}")
    print(f"Ambiguity Note:        {res1.ambiguity_note}")
    print(f"Needs Clarification:   {res1.needs_clarification}")
    if res1.clarification_question:
        print(f"Clarification Q:       {res1.clarification_question}")

    print("\nExpected Topics:")
    print(f"{'#':<3} | {'Key':<26} | {'Label':<28} | {'Imp':<4} | {'Critical':<8} | {'Description'}")
    print("-" * 115)
    for idx, t in enumerate(res1.expected_topics, 1):
        crit = "YES" if t.is_critical else "no"
        # Print each topic on one line with any newlines in description replaced by spaces
        clean_desc = " ".join(t.description.split())
        clean_label = " ".join(t.label.split())
        print(f"{idx:<3} | {t.key:<26} | {clean_label:<28} | {t.importance:<4} | {crit:<8} | {clean_desc}")
    print("-" * 115)

    # Dump the raw topics as JSON to confirm topic 1 is well-formed and valid
    print("\nRaw Topics JSON (Hygiene Verification):")
    raw_topics_data = [t.model_dump() for t in res1.expected_topics]
    print(json.dumps(raw_topics_data, indent=2))

    # Second run (should be instant SQLite cache hit)
    print("\n[Run 2] Executing understand() again with identical question...")
    t1 = time.perf_counter()
    res2 = await understand(question)
    elapsed2 = (time.perf_counter() - t1) * 1000.0
    print(f"Elapsed: {elapsed2:.1f}ms")
    if elapsed2 < 80.0 and len(res1.expected_topics) == len(res2.expected_topics):
        print(">> CACHE HIT verified: Response retrieved instantly from SQLite cache!")
    else:
        print(f">> Second run completed in {elapsed2:.1f}ms")

    print("\n" + "=" * 95)


if __name__ == "__main__":
    q = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "What should I verify before applying for the PM YASASVI scholarship?"
    )
    asyncio.run(run_demo(q))

