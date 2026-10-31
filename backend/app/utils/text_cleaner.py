from __future__ import annotations

import re
from typing import Optional

from bs4 import BeautifulSoup

import trafilatura


def clean_html(html: str, url: str) -> str:
    """
    Extract main text from HTML.

    Tries trafilatura first; falls back to BeautifulSoup stripping if the
    result is absent or very short.
    """
    extracted = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        url=url,
    )
    if extracted and len(extracted.strip()) >= 100:
        return extracted.strip()

    # BeautifulSoup fallback
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
        tag.decompose()
    text = soup.get_text(separator="\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)


def extract_title(html: str) -> Optional[str]:
    """Return the page title from og:title meta or <title> tag."""
    soup = BeautifulSoup(html, "html.parser")

    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        return og_title["content"].strip()

    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        return title_tag.string.strip()

    return None
