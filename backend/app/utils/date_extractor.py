from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

from bs4 import BeautifulSoup
from dateutil import parser as dateutil_parser


def extract_date(html: str, url: str) -> tuple[Optional[datetime], str]:
    """
    Extract a publication/modification date from HTML or URL.

    Checks in this order:
    1. Meta tags (og:updated_time, article:published_time, article:modified_time)
    2. JSON-LD (datePublished, dateModified)
    3. Visible date patterns near the top of the text
    4. URL path pattern (e.g. /2024/03/)

    Returns (datetime | None, origin) where origin is one of:
    "meta", "jsonld", "visible_text", "url_pattern", "none".
    """
    soup = BeautifulSoup(html, "html.parser")

    # 1. Meta tags
    meta_properties = [
        "og:updated_time",
        "article:modified_time",
        "article:published_time",
    ]
    for prop in meta_properties:
        tag = soup.find("meta", property=prop)
        if tag and tag.get("content"):
            dt = _safe_parse(tag["content"])
            if dt:
                return dt, "meta"
    # Also check name-based meta tags
    meta_names = ["publish-date", "date", "DC.date", "pubdate"]
    for name in meta_names:
        tag = soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            dt = _safe_parse(tag["content"])
            if dt:
                return dt, "meta"

    # 2. JSON-LD
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
            if not isinstance(data, dict):
                # Could be a list
                if isinstance(data, list):
                    for item in data:
                        result = _extract_jsonld_date(item)
                        if result:
                            return result, "jsonld"
                continue
            result = _extract_jsonld_date(data)
            if result:
                return result, "jsonld"
        except (json.JSONDecodeError, TypeError):
            continue

    # 3. Visible text near top of the document
    text_top = soup.get_text()[:3000]
    dt = _extract_from_text(text_top)
    if dt:
        return dt, "visible_text"

    # 4. URL pattern
    url_match = re.search(r"/(\d{4})/(\d{1,2})/", url)
    if url_match:
        try:
            year, month = int(url_match.group(1)), int(url_match.group(2))
            if 2000 <= year <= 2100 and 1 <= month <= 12:
                return datetime(year, month, 1), "url_pattern"
        except ValueError:
            pass
    # Year-only in URL
    url_year = re.search(r"/(\d{4})/", url)
    if url_year:
        try:
            year = int(url_year.group(1))
            if 2000 <= year <= 2100:
                return datetime(year, 1, 1), "url_pattern"
        except ValueError:
            pass

    return None, "none"


def _extract_jsonld_date(data: dict) -> Optional[datetime]:
    for field in ("dateModified", "datePublished"):
        val = data.get(field)
        if val:
            dt = _safe_parse(val)
            if dt:
                return dt
    return None


def _extract_from_text(text: str) -> Optional[datetime]:
    patterns = [
        r"\b(\d{4}-\d{2}-\d{2})\b",                          # YYYY-MM-DD
        r"\b(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})\b",
        r"\b((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})\b",
        r"\b(\d{2}/\d{2}/\d{4})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            dt = _safe_parse(m.group(1))
            if dt:
                return dt
    return None


def _safe_parse(value: str) -> Optional[datetime]:
    try:
        return dateutil_parser.parse(value, ignoretz=True)
    except (ValueError, OverflowError, TypeError):
        return None
