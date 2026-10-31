"""
date_extraction.py — Deterministic published date, cycle year, and freshness status extraction.

Order of preference for date:
1. meta tags (article:modified_time, article:published_time, og:updated_time, dateModified, datePublished, last-modified)
2. JSON-LD (dateModified, datePublished)
3. provider-supplied date
4. visible text patterns near top/bottom
5. URL pattern (/2024/05/, /2024-05-14/)
otherwise none

NO LLM is used in this module.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Literal, Optional, Tuple
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from dateutil import parser

DateOrigin = Literal["meta", "jsonld", "visible_text", "url_pattern", "none"]
DateStatus = Literal["fresh", "stale", "undated"]

MIN_VALID_YEAR = 2000


def _parse_raw_date(date_str: str, dayfirst: bool = True) -> Optional[date]:
    """Parse string to date. Reject dates before 2000 or in the future."""
    if not date_str or not date_str.strip():
        return None
    try:
        clean_str = date_str.strip()
        # Remove trailing timezones or noise if needed
        dt = parser.parse(clean_str, fuzzy=True, dayfirst=dayfirst)
        d = dt.date()
        today = date.today()
        if d.year < MIN_VALID_YEAR or d > today:
            return None
        return d
    except Exception:
        return None


def extract_published_date(
    html: Optional[str],
    text: str,
    url: str,
    provider_date: Optional[str] = None,
) -> Tuple[Optional[date], DateOrigin]:
    """Extract published/modified date from HTML meta tags, JSON-LD, provider date, text patterns, or URL."""
    soup: Optional[BeautifulSoup] = None
    if html:
        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            soup = None

    # 1. Meta Tags (prefer modified/updated over published)
    if soup:
        meta_keys_modified = [
            ("property", "article:modified_time"),
            ("property", "og:updated_time"),
            ("name", "last-modified"),
            ("name", "dateModified"),
            ("http-equiv", "last-modified"),
        ]
        for attr, key in meta_keys_modified:
            tag = soup.find("meta", attrs={attr: re.compile(f"^{re.escape(key)}$", re.I)})
            if tag and tag.get("content"):
                d = _parse_raw_date(tag["content"])
                if d:
                    return d, "meta"

        meta_keys_published = [
            ("property", "article:published_time"),
            ("name", "article:published_time"),
            ("name", "datePublished"),
            ("name", "pubdate"),
            ("name", "date"),
        ]
        for attr, key in meta_keys_published:
            tag = soup.find("meta", attrs={attr: re.compile(f"^{re.escape(key)}$", re.I)})
            if tag and tag.get("content"):
                d = _parse_raw_date(tag["content"])
                if d:
                    return d, "meta"

    # 2. JSON-LD scripts
    if soup:
        for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(script.string or "")
                # Could be a dict or a list of dicts
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    # Prefer modified over published
                    for k in ("dateModified", "datePublished", "uploadDate"):
                        val = item.get(k)
                        if val and isinstance(val, str):
                            d = _parse_raw_date(val)
                            if d:
                                return d, "jsonld"
            except Exception:
                continue

    # 3. Provider-supplied date (e.g. from Tavily)
    if provider_date:
        d = _parse_raw_date(provider_date)
        if d:
            return d, "meta"  # treat provider metadata as meta origin

    # 4. Visible text patterns near top (first 1000 chars) or bottom (last 1000 chars)
    snippets_to_scan = []
    if text:
        top_snippet = text[:1200]
        bottom_snippet = text[-1000:] if len(text) > 1200 else ""
        snippets_to_scan = [top_snippet, bottom_snippet]

    text_date_regex = re.compile(
        r"(?:last\s+updated|updated\s+on|posted\s+on|published\s+on|date\s*:?)\s*[:\-]?\s*"
        r"([0-9]{1,2}[\/\-\.][0-9]{1,2}[\/\-\.][0-9]{4}|[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4}|[A-Za-z]{3,9}\s+[0-9]{1,2},\s*[0-9]{4})",
        re.I,
    )
    for snip in snippets_to_scan:
        matches = text_date_regex.findall(snip)
        for m in matches:
            d = _parse_raw_date(m, dayfirst=True)
            if d:
                return d, "visible_text"

    # 5. URL pattern: /2024/05/, /2024-05-14/, /2023_11_20/
    url_date_regex = re.compile(r"\/((?:20[0-2][0-9])[\/\-_](?:0[1-9]|1[0-2])(?:[\/\-_](?:0[1-9]|[12][0-9]|3[01]))?)\b")
    parsed_url = urlparse(url)
    m_url = url_date_regex.search(parsed_url.path)
    if m_url:
        d_str = m_url.group(1).replace("_", "-").replace("/", "-")
        # If year and month only, e.g. 2024-05 -> 2024-05-01
        if len(d_str.split("-")) == 2:
            d_str = f"{d_str}-01"
        d = _parse_raw_date(d_str, dayfirst=False)
        if d:
            return d, "url_pattern"

    return None, "none"


def extract_cycle_year(title: str, text: str) -> Optional[str]:
    """Extract academic, application, or fiscal cycle year from title and text.

    Matches patterns like:
      - 2025-26, 2025-2026, 2024-25
      - AY 2025-26, AY 2025
      - Batch of 2025, Session 2025-26
      - FY 2025-26, Class of 2026

    Returns normalized string like "2025-26" or "2025".
    """
    sample = f"{title}\n{text[:2000]}"

    # Pattern A: 2025-26 or 2025-2026
    span_regex = re.compile(r"\b(20[2-3][0-9])\s*[-–\/]\s*(20[2-3][0-9]|[2-3][0-9])\b")
    m_span = span_regex.search(sample)
    if m_span:
        y1 = m_span.group(1)
        y2 = m_span.group(2)
        if len(y2) == 4:
            y2 = y2[-2:]
        return f"{y1}-{y2}"

    # Pattern B: Explicit keywords like AY 2025, Session 2025, Batch of 2025
    keyword_year_regex = re.compile(
        r"\b(?:AY|academic\s+year|batch\s+of|session|class\s+of|FY|scheme\s+year)\s*[:\-]?\s*(20[2-3][0-9])\b",
        re.I,
    )
    m_kw = keyword_year_regex.search(sample)
    if m_kw:
        return m_kw.group(1)

    return None


def freshness_status(
    published: Optional[date],
    cycle_year: Optional[str],
    today: date,
    stale_months: int,
) -> DateStatus:
    """Determine freshness status: fresh, stale, or undated.

    Rule:
    - If no published date is found and no cycle year exists: "undated".
    - A page older than `stale_months` is considered "stale".
    - EXCEPTION: If the published date is older than `stale_months`, BUT the page
      explicitly contains a cycle year corresponding to the current or upcoming
      cycle (>= current calendar year), it stays "fresh".
      Conversely, if cycle year is strictly in the past, it is "stale".
    """
    current_year = today.year

    # Check cycle year first if published date is missing
    if published is None:
        if cycle_year is not None:
            # Parse start year of cycle
            start_year = int(cycle_year.split("-")[0])
            if start_year >= current_year - 1:
                return "fresh"
            return "stale"
        return "undated"

    # Compute age in months
    age_months = (today.year - published.year) * 12 + (today.month - published.month)

    if age_months > stale_months:
        # Check if text contains current or future cycle
        if cycle_year is not None:
            try:
                start_year = int(cycle_year.split("-")[0])
                if start_year >= current_year:
                    return "fresh"
            except Exception:
                pass
        return "stale"

    # Even if published date is recent, check if cycle year is distinctly old
    if cycle_year is not None:
        try:
            start_year = int(cycle_year.split("-")[0])
            if start_year < current_year - 2:
                return "stale"
        except Exception:
            pass

    return "fresh"

