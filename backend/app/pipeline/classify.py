"""
classify.py — Deterministic source classification (official, news, aggregator, blog, forum, unknown).

Classification is a display hint and ranking signal only, never a final verdict of truth.
"""
from __future__ import annotations

import re
from typing import Literal
from urllib.parse import urlparse

from .domain_lists import (
    AGGREGATOR_DOMAINS,
    AGGREGATOR_TITLE_PATTERNS,
    BLOG_DOMAINS,
    FORUM_DOMAINS,
    NEWS_DOMAINS,
    OFFICIAL_SUFFIXES,
)

SourceClass = Literal["official", "news", "aggregator", "blog", "forum", "unknown"]


def extract_domain(url: str) -> str:
    """Extract clean lowercase host domain from a URL."""
    try:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = (parsed.hostname or "").lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _entity_matches_domain(entity: str, domain: str) -> bool:
    """Check if normalized words or acronyms from the entity appear strongly in the domain."""
    if not entity or not domain:
        return False

    clean_domain = re.sub(r"[^a-z0-9]", "", domain.lower())
    words = [w.lower() for w in re.findall(r"[a-zA-Z0-9]+", entity)]

    # Acronym match: e.g. "National Scholarship Portal" -> "nsp"
    if len(words) >= 2:
        acronym = "".join(w[0] for w in words)
        if len(acronym) >= 3 and acronym in clean_domain:
            return True

    # Multi-word match: e.g. "PM YASASVI" -> "pmyasasvi" or "yasasvi"
    for w in words:
        if len(w) >= 4 and w in clean_domain:
            return True

    return False


def classify_source(url: str, title: str = "", entity: str = "") -> SourceClass:
    """Classify a web source into one of: official, news, aggregator, blog, forum, unknown."""
    if not url:
        return "unknown"

    domain = extract_domain(url)
    lower_title = title.lower() if title else ""

    # 1. Official check
    # Check official TLD / suffixes
    if any(domain.endswith(suffix) for suffix in OFFICIAL_SUFFIXES):
        return "official"

    # Domain strongly matches entity or its official organization name
    if entity and _entity_matches_domain(entity, domain):
        # Ensure it's not a known blog or forum hosting user content
        if not any(b in domain for b in BLOG_DOMAINS) and not any(f in domain for f in FORUM_DOMAINS):
            return "official"

    # 2. News check
    if domain in NEWS_DOMAINS or any(domain.endswith(f".{nd}") for nd in NEWS_DOMAINS):
        return "news"

    # 3. Forum check
    if any(f in domain for f in FORUM_DOMAINS):
        return "forum"

    # 4. Blog check
    if any(b in domain for b in BLOG_DOMAINS):
        return "blog"

    # 5. Aggregator check
    if domain in AGGREGATOR_DOMAINS or any(domain.endswith(f".{ad}") for ad in AGGREGATOR_DOMAINS):
        return "aggregator"

    if any(p in lower_title for p in AGGREGATOR_TITLE_PATTERNS):
        return "aggregator"

    return "unknown"


def is_primary_candidate(source_or_url: str | object, entity: str) -> bool:
    """Check if a source is a candidate for being the primary official authority for an entity."""
    if isinstance(source_or_url, str):
        url = source_or_url
        s_class = classify_source(url, entity=entity)
    else:
        url = getattr(source_or_url, "url", "") or ""
        s_class = getattr(source_or_url, "source_class", "unknown")

    if s_class == "official":
        return True

    domain = extract_domain(url)
    if entity and _entity_matches_domain(entity, domain):
        return True

    return False

