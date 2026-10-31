#!/usr/bin/env python3
"""
scripts/collect_sources_demo.py
───────────────────────────────
Developer CLI demo script for Phase 1+9 source acquisition:
Generates queries -> collects candidates -> fetches/cleans pages -> extracts dates -> chunks passages.
Prints a formatted table and all warnings.

Usage:
    python scripts/collect_sources_demo.py "National Scholarship Portal"
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

from dotenv import load_dotenv

env_path = backend_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)

from app.models import ExpectedTopic
from app.pipeline.fetch_clean import fetch_sources_in_parallel
from app.pipeline.source_acquisition import collect_candidates


async def run_demo(entity: str):
    print("=" * 110)
    print(f"Traceable Source Acquisition Demo — Entity: {entity!r}")
    print("=" * 110)

    # 1. Build sample topics for this entity
    sample_topics = [
        ExpectedTopic(
            key="eligibility_criteria",
            label="Eligibility Criteria",
            importance=5,
            description="Who is eligible to apply for this scholarship or scheme",
        ),
        ExpectedTopic(
            key="application_deadline",
            label="Application Deadline",
            importance=5,
            description="Last date and timeline to apply",
        ),
        ExpectedTopic(
            key="required_documents",
            label="Required Documents",
            importance=4,
            description="Documents, certificates, and ID proofs needed",
        ),
        ExpectedTopic(
            key="renewal_policy",
            label="Renewal Policy",
            importance=3,
            description="Conditions and process to renew for subsequent years",
        ),
    ]

    t0 = time.perf_counter()

    # 2. Collect candidate sources
    print(f"\n[1/2] Searching Tavily and collecting top candidates for {entity!r}...")
    collect_res = await collect_candidates(
        entity=entity,
        topics=sample_topics,
        max_sources=8,
        use_cache=True,
    )
    candidates = collect_res.candidates
    warnings = list(collect_res.warnings)

    print(f"  Found {len(candidates)} candidate URLs.")

    # 3. Fetch, clean, date, chunk in parallel
    print(f"\n[2/2] Fetching, cleaning, extracting dates, and chunking {len(candidates)} sources...")
    sources = await fetch_sources_in_parallel(
        candidates=candidates,
        entity=entity,
        max_concurrency=5,
        use_cache=True,
    )

    elapsed_s = time.perf_counter() - t0

    # 4. Print Results Table
    header = (
        f"{'ID':<4} | {'Class':<10} | {'Domain':<24} | {'Status':<7} | "
        f"{'Date (Origin)':<20} | {'Freshness':<9} | {'Cycle':<8} | "
        f"{'Words':<6} | {'Passages':<8} | {'Snippet (first 100 chars)'}"
    )
    separator = "-" * 135

    print("\n" + separator)
    print(header)
    print(separator)

    for src in sources:
        sid = src.id
        sclass = src.source_class
        domain = (src.domain or "n/a")[:24]
        status = src.fetch_status
        d_str = src.published_date.strftime("%Y-%m-%d") if src.published_date else "None"
        d_orig = f"{d_str} ({src.date_origin})"[:20]
        fresh = src.date_status
        cycle = str(src.cycle_year or "None")[:8]
        
        total_words = sum(len(p.text.split()) for p in src.passages)
        p_count = len(src.passages)
        
        snippet = ""
        if src.passages:
            first_txt = src.passages[0].text.replace("\n", " ")
            snippet = first_txt[:100] + ("..." if len(first_txt) > 100 else "")
        elif src.error_message:
            snippet = f"Error: {src.error_message[:90]}"

        row = (
            f"{sid:<4} | {sclass:<10} | {domain:<24} | {status:<7} | "
            f"{d_orig:<20} | {fresh:<9} | {cycle:<8} | "
            f"{total_words:<6} | {p_count:<8} | {snippet}"
        )
        print(row)

    print(separator)
    print(f"Total time elapsed: {elapsed_s:.2f}s")

    # 5. Print Warnings
    if warnings:
        print("\nWarnings:")
        for w in warnings:
            print(f"  • {w}")
    else:
        print("\nWarnings: None")

    print("=" * 110 + "\n")


if __name__ == "__main__":
    target_entity = sys.argv[1] if len(sys.argv) > 1 else "National Scholarship Portal"
    asyncio.run(run_demo(target_entity))

