"""
queries.py — Deterministic, template-based search query generation.

NO LLM is used in this module.
"""
from __future__ import annotations

import re
from typing import List

from ..models import ExpectedTopic


def _clean_token(text: str) -> str:
    """Normalize text into clean words."""
    return re.sub(r"\s+", " ", text).strip()


def generate_queries(
    entity: str,
    topics: List[ExpectedTopic],
    max_queries: int = 6,
) -> List[str]:
    """Generate search queries for an entity and expected topics.

    Rules:
    - Template-based, purely deterministic code.
    - Always includes one query aimed at the official site / portal.
    - Always includes one query aimed at recent notices / updates.
    - Orders expected topics by importance (highest first).
    - Deduplicates and caps at max_queries.
    """
    clean_entity = _clean_token(entity)
    queries: list[str] = []

    # 1. Primary official search query
    queries.append(f"{clean_entity} official website portal")

    # 2. Topic-driven queries (sorted by importance descending)
    sorted_topics = sorted(topics, key=lambda t: t.importance, reverse=True)

    for topic in sorted_topics:
        key = topic.key.lower()
        label = topic.label.lower()

        if "eligib" in key or "eligib" in label or "who can" in label:
            q = f"{clean_entity} eligibility criteria"
        elif "dead" in key or "date" in key or "dead" in label or "date" in label or "schedul" in label:
            q = f"{clean_entity} deadline dates schedule"
        elif "doc" in key or "doc" in label or "certif" in label:
            q = f"{clean_entity} documents required"
        elif "appl" in key or "appl" in label or "how to" in label or "proc" in label:
            q = f"{clean_entity} application process how to apply"
        elif "renew" in key or "renew" in label:
            q = f"{clean_entity} renewal criteria terms"
        elif "amount" in key or "benefit" in key or "amount" in label or "benefit" in label:
            q = f"{clean_entity} scholarship amount benefits"
        elif "select" in key or "merit" in label or "select" in label:
            q = f"{clean_entity} selection process merit list"
        else:
            q = f"{clean_entity} {topic.label}"

        clean_q = _clean_token(q)
        if clean_q not in queries:
            queries.append(clean_q)

    # 3. Recent notices & official updates query
    notice_q = _clean_token(f"{clean_entity} latest notification notice updates")
    if notice_q not in queries:
        queries.append(notice_q)

    # Ensure deduplicated list, preserving order, capped at max_queries
    seen = set()
    deduped: list[str] = []
    for q in queries:
        q_norm = q.lower()
        if q_norm not in seen:
            seen.add(q_norm)
            deduped.append(q)
        if len(deduped) >= max_queries:
            break

    return deduped

