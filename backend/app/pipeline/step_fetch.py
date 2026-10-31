from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
from uuid import uuid4

import httpx

from ..models import Source, Passage
from ..utils.text_cleaner import clean_html, extract_title
from ..utils.date_extractor import extract_date
from ..utils.source_classifier import classify_source
from ..utils.chunker import chunk_text
from ..utils.freshness import compute_freshness
from ..config import settings

logger = logging.getLogger(__name__)

_TIMEOUT = 15.0
_BLOCKED_STATUS = {401, 403, 406, 429}


async def fetch_url(url: str, source_id: str, stale_months: int) -> Source:
    """
    Fetch a URL and return a populated Source object.
    """
    parsed = urlparse(url)
    domain = parsed.netloc or url

    source = Source(
        id=source_id,
        type="url",
        url=url,
        domain=domain,
        fetched_at=datetime.utcnow(),
    )

    try:
        async with httpx.AsyncClient(
            timeout=_TIMEOUT, follow_redirects=True, headers={"User-Agent": "Traceable/0.1"}
        ) as client:
            response = await client.get(url)

        if response.status_code in _BLOCKED_STATUS:
            source.fetch_status = "blocked"
            source.error_message = f"HTTP {response.status_code}"
            return source

        response.raise_for_status()
        html = response.text

        if not html or not html.strip():
            source.fetch_status = "empty"
            return source

        # Extract text and title
        text = clean_html(html, url)
        title = extract_title(html)
        source.title = title or domain

        if not text or len(text.strip()) < 50:
            source.fetch_status = "empty"
            return source

        # Date extraction
        published_date, date_origin = extract_date(html, url)
        source.published_date = published_date
        source.date_origin = date_origin  # type: ignore[assignment]

        # Source classification
        source_class = classify_source(domain, url)
        source.source_class = source_class  # type: ignore[assignment]

        # Freshness
        source.date_status = compute_freshness(published_date, source.cycle_year, stale_months)  # type: ignore[assignment]

        # Chunking
        source.passages = chunk_text(text, source_id)
        source.fetch_status = "ok"

    except httpx.TimeoutException:
        source.fetch_status = "failed"
        source.error_message = "Request timed out"
    except httpx.HTTPStatusError as exc:
        source.fetch_status = "failed"
        source.error_message = f"HTTP {exc.response.status_code}"
    except Exception as exc:
        source.fetch_status = "failed"
        source.error_message = str(exc)
        logger.warning("fetch_url error for %s: %s", url, exc)

    return source


async def fetch_all(urls: list[str], stale_months: int) -> list[Source]:
    """
    Fetch all URLs concurrently. Individual errors are caught and reflected
    in the Source.fetch_status field.
    """
    tasks = [
        fetch_url(url, str(uuid4()), stale_months)
        for url in urls
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    sources: list[Source] = []
    for url, result in zip(urls, results):
        if isinstance(result, Exception):
            parsed = urlparse(url)
            sources.append(
                Source(
                    id=str(uuid4()),
                    type="url",
                    url=url,
                    domain=parsed.netloc or url,
                    fetch_status="failed",
                    error_message=str(result),
                    fetched_at=datetime.utcnow(),
                )
            )
        else:
            sources.append(result)

    return sources
