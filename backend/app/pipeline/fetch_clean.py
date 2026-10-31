"""
fetch_clean.py — Source fetching, SSRF guard, HTML/PDF extraction, and cleaning.

NO LLM is used in this module.
Never crashes on a bad source; records fetch_status and error_message.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import ipaddress
import logging
import re
import socket
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import aiosqlite
import httpx
import pdfplumber
import trafilatura
from bs4 import BeautifulSoup

from ..config import settings
from ..models import Source
from .chunking import chunk_text
from .classify import classify_source, extract_domain
from .date_extraction import (
    extract_cycle_year,
    extract_published_date,
    freshness_status,
)
from .errors import SSRFBlockedError
from .search import SearchResult

logger = logging.getLogger("traceable.fetch")

MAX_SOURCE_WORDS = 15000
MAX_DOWNLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 (Traceable/0.1)"
)

# ---------------------------------------------------------------------------
# SSRF Guard
# ---------------------------------------------------------------------------

def is_ip_private_or_restricted(ip_str: str) -> bool:
    """Check if an IP address belongs to loopback, link-local, private, or reserved ranges."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )
    except ValueError:
        return True


def validate_url_safety(url: str) -> None:
    """Validate that URL uses http/https and does not resolve to private/loopback IP ranges."""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise SSRFBlockedError(f"Unsupported protocol {scheme!r}; only http and https are allowed")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise SSRFBlockedError("Invalid URL: missing hostname")

    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise SSRFBlockedError(f"SSRF Refusal: host {hostname!r} is localhost")

    # Resolve hostname to IP addresses
    try:
        addr_info = socket.getaddrinfo(hostname, None)
        for _, _, _, _, sockaddr in addr_info:
            ip_addr = sockaddr[0]
            if is_ip_private_or_restricted(ip_addr):
                raise SSRFBlockedError(
                    f"SSRF Refusal: host {hostname!r} resolves to restricted IP {ip_addr!r}"
                )
    except socket.gaierror as e:
        raise SSRFBlockedError(f"DNS resolution failure for host {hostname!r}: {e}") from e


# ---------------------------------------------------------------------------
# SQLite Page Cache
# ---------------------------------------------------------------------------

_initialized_page_dbs: set[str] = set()
_page_cache_lock = asyncio.Lock()


async def _init_page_cache(db_path: str) -> None:
    abs_path = str(Path(db_path).resolve())
    if abs_path in _initialized_page_dbs:
        return
    async with _page_cache_lock:
        if abs_path in _initialized_page_dbs:
            return
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(abs_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS page_cache (
                    url_hash TEXT PRIMARY KEY,
                    url TEXT NOT NULL,
                    html TEXT,
                    text TEXT NOT NULL,
                    title TEXT,
                    content_type TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.commit()
        _initialized_page_dbs.add(abs_path)


def _compute_url_hash(url: str) -> str:
    return hashlib.sha256(url.strip().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Text Extraction Helpers
# ---------------------------------------------------------------------------

def extract_title_from_html(html: str) -> str:
    """Extract page title from og:title, twitter:title, or <title> tag."""
    if not html:
        return ""
    try:
        soup = BeautifulSoup(html, "html.parser")
        # 1. Open Graph title
        og_t = soup.find("meta", property="og:title")
        if og_t and og_t.get("content"):
            return og_t["content"].strip()
        # 2. Standard <title>
        if soup.title and soup.title.string:
            return soup.title.string.strip()
    except Exception:
        pass
    return ""


def clean_html_to_text(html: str) -> str:
    """Extract clean readable text from HTML using trafilatura with BeautifulSoup fallback."""
    if not html:
        return ""

    # Primary extractor: trafilatura
    try:
        extracted = trafilatura.extract(
            html,
            include_links=False,
            include_comments=False,
            include_tables=True,
            output_format="txt",
        )
        if extracted and len(extracted.strip()) > 100:
            return extracted.strip()
    except Exception:
        pass

    # Fallback extractor: BeautifulSoup with boilerpipe removal
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Collapse multiple blank lines
        cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
        return cleaned
    except Exception:
        return ""


def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pdfplumber."""
    pages_text: list[str] = []
    try:
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                txt = page.extract_text()
                if txt:
                    pages_text.append(txt.strip())
        return "\n\n".join(pages_text).strip()
    except Exception as e:
        logger.warning("PDF extraction failed: %s", e)
        return ""


# ---------------------------------------------------------------------------
# Source Builders
# ---------------------------------------------------------------------------

async def source_from_text(text: str, title: str, source_id: str) -> Source:
    """Construct a Source object from pasted raw text."""
    clean_text = text.strip()
    today = date.today()

    # Cap word length
    words = clean_text.split()
    if len(words) > MAX_SOURCE_WORDS:
        clean_text = " ".join(words[:MAX_SOURCE_WORDS])

    pub_date, date_orig = extract_published_date(None, clean_text, "", None)
    c_year = extract_cycle_year(title, clean_text)
    f_status = freshness_status(pub_date, c_year, today, settings.STALE_MONTHS)

    passages = chunk_text(clean_text, source_id, title=title)

    dt_published = (
        datetime.combine(pub_date, datetime.min.time(), tzinfo=timezone.utc)
        if pub_date else None
    )

    return Source(
        id=source_id,
        type="text",
        url=None,
        title=title or "Pasted Text",
        domain=None,
        source_class="unknown",
        fetched_at=datetime.now(timezone.utc),
        published_date=dt_published,
        date_origin=date_orig,
        date_status=f_status,
        cycle_year=c_year,
        fetch_status="ok" if clean_text else "empty",
        passages=passages,
    )


async def source_from_pdf(data: bytes, filename: str, source_id: str) -> Source:
    """Construct a Source object from uploaded PDF file bytes."""
    extracted = extract_pdf_text(data)
    today = date.today()

    words = extracted.split()
    if len(words) > MAX_SOURCE_WORDS:
        extracted = " ".join(words[:MAX_SOURCE_WORDS])

    pub_date, date_orig = extract_published_date(None, extracted, filename, None)
    c_year = extract_cycle_year(filename, extracted)
    f_status = freshness_status(pub_date, c_year, today, settings.STALE_MONTHS)

    passages = chunk_text(extracted, source_id, title=filename)

    dt_published = (
        datetime.combine(pub_date, datetime.min.time(), tzinfo=timezone.utc)
        if pub_date else None
    )

    return Source(
        id=source_id,
        type="pdf",
        url=None,
        title=filename,
        domain=None,
        source_class="official" if ".gov" in filename.lower() else "unknown",
        fetched_at=datetime.now(timezone.utc),
        published_date=dt_published,
        date_origin=date_orig,
        date_status=f_status,
        cycle_year=c_year,
        fetch_status="ok" if extracted else "empty",
        error_message=None if extracted else "No readable text found in PDF document",
        passages=passages,
    )


async def build_source(
    candidate: SearchResult | str,
    source_id: str,
    entity: str = "",
    *,
    use_cache: bool = True,
    http_client: Optional[httpx.AsyncClient] = None,
) -> Source:
    """Fetch, clean, date, classify, and chunk a web page or candidate SearchResult.

    Never crashes on failure: populates fetch_status and error_message.
    """
    url = candidate.url if isinstance(candidate, SearchResult) else str(candidate).strip()
    title_hint = candidate.title if isinstance(candidate, SearchResult) else ""
    provider_content = candidate.content if isinstance(candidate, SearchResult) else None
    provider_date = candidate.published_date if isinstance(candidate, SearchResult) else None

    domain = extract_domain(url)
    s_class = classify_source(url, title=title_hint, entity=entity)
    today = date.today()
    db_path = settings.SQLITE_DB_PATH

    raw_html: Optional[str] = None
    clean_text = ""
    title = title_hint
    fetch_status = "ok"
    err_message: Optional[str] = None

    # 1. If provider already returned full raw content, use it directly!
    if provider_content and len(provider_content.strip()) > 150:
        if "<html" in provider_content.lower():
            raw_html = provider_content
            clean_text = clean_html_to_text(provider_content)
            title = extract_title_from_html(provider_content) or title_hint
        else:
            clean_text = provider_content.strip()

    # 2. Check SQLite Page Cache
    if not clean_text and use_cache:
        await _init_page_cache(db_path)
        url_hash = _compute_url_hash(url)
        try:
            async with aiosqlite.connect(db_path) as db:
                async with db.execute(
                    "SELECT html, text, title, created_at FROM page_cache WHERE url_hash = ?",
                    (url_hash,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        cached_html, cached_text, cached_title, created_at_str = row
                        created_at = datetime.fromisoformat(created_at_str)
                        if datetime.now(timezone.utc) - created_at < timedelta(hours=settings.PAGE_CACHE_TTL_HOURS):
                            raw_html = cached_html
                            clean_text = cached_text
                            title = cached_title or title_hint
        except Exception as e:
            logger.warning("Page cache read error for %s: %s", url, e)

    # 3. Live Web Fetch with SSRF Guard
    if not clean_text:
        try:
            # SSRF validation before request
            validate_url_safety(url)

            # Perform HTTP request
            headers = {"User-Agent": DEFAULT_USER_AGENT}
            client_to_use = http_client or httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                max_redirects=5,
                headers=headers,
            )

            async def _fetch():
                # Re-validate redirect target URLs if redirects occur
                async with client_to_use:
                    async with client_to_use.stream("GET", url) as resp:
                        # Check final URL after redirects
                        validate_url_safety(str(resp.url))

                        if resp.status_code == 403:
                            return None, "blocked", f"HTTP 403 Forbidden (bot protection / access denied)"
                        if resp.status_code >= 400:
                            return None, "failed", f"HTTP {resp.status_code} Error"

                        content_type = resp.headers.get("Content-Type", "").lower()
                        # Enforce max download size
                        downloaded = bytearray()
                        async for chunk in resp.aiter_bytes():
                            downloaded.extend(chunk)
                            if len(downloaded) > MAX_DOWNLOAD_BYTES:
                                break

                        return bytes(downloaded), content_type, None

            # Run with or without closing injected client
            if http_client:
                resp_bytes, content_type_or_status, err = await _fetch_with_existing_client(
                    http_client, url, headers
                )
            else:
                resp_bytes, content_type_or_status, err = await _fetch()

            if err:
                fetch_status = content_type_or_status
                err_message = err
            elif resp_bytes:
                content_type = content_type_or_status
                if "application/pdf" in content_type or url.lower().endswith(".pdf"):
                    clean_text = extract_pdf_text(resp_bytes)
                else:
                    raw_html = resp_bytes.decode("utf-8", errors="replace")
                    clean_text = clean_html_to_text(raw_html)
                    title = extract_title_from_html(raw_html) or title_hint

                if not clean_text or len(clean_text.strip()) < 80:
                    fetch_status = "empty"
                    err_message = "Page retrieved but contained almost no readable text (likely JS-only)"

        except SSRFBlockedError as ssrf_err:
            fetch_status = "blocked"
            err_message = str(ssrf_err)
        except (httpx.TimeoutException, asyncio.TimeoutError):
            fetch_status = "failed"
            err_message = "Request timed out after 10.0s"
        except Exception as exc:
            fetch_status = "failed"
            err_message = f"Network fetch error: {exc}"

    # 4. Cap word length at 15,000 words
    if clean_text:
        words = clean_text.split()
        if len(words) > MAX_SOURCE_WORDS:
            clean_text = " ".join(words[:MAX_SOURCE_WORDS])

    # 5. Extract published date & cycle year
    pub_date, date_origin = extract_published_date(raw_html, clean_text, url, provider_date)
    cycle_yr = extract_cycle_year(title, clean_text)
    f_status = freshness_status(pub_date, cycle_yr, today, settings.STALE_MONTHS)

    # 6. Chunk text into passages
    passages = chunk_text(clean_text, source_id, title=title) if clean_text else []

    dt_pub = (
        datetime.combine(pub_date, datetime.min.time(), tzinfo=timezone.utc)
        if pub_date else None
    )

    # 7. Write to Page Cache on success
    if fetch_status == "ok" and clean_text and use_cache:
        try:
            now_str = datetime.now(timezone.utc).isoformat()
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO page_cache
                    (url_hash, url, html, text, title, content_type, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (_compute_url_hash(url), url, raw_html, clean_text, title, "text/html", now_str),
                )
                await db.commit()
        except Exception as cache_err:
            logger.warning("Page cache write error: %s", cache_err)

    return Source(
        id=source_id,
        type="search" if isinstance(candidate, SearchResult) else "url",
        url=url,
        title=title or url,
        domain=domain,
        source_class=s_class,
        fetched_at=datetime.now(timezone.utc),
        published_date=dt_pub,
        date_origin=date_origin,
        date_status=f_status,
        cycle_year=cycle_yr,
        fetch_status=fetch_status,
        error_message=err_message,
        passages=passages,
    )


async def _fetch_with_existing_client(
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str],
) -> Tuple[Optional[bytes], str, Optional[str]]:
    """Helper for fetching with a shared/injected httpx client."""
    resp = await client.get(url, headers=headers, timeout=10.0, follow_redirects=True)
    validate_url_safety(str(resp.url))
    if resp.status_code == 403:
        return None, "blocked", "HTTP 403 Forbidden"
    if resp.status_code >= 400:
        return None, "failed", f"HTTP {resp.status_code}"
    content_type = resp.headers.get("Content-Type", "").lower()
    return resp.content, content_type, None


async def fetch_sources_in_parallel(
    candidates: List[SearchResult | str],
    entity: str = "",
    max_concurrency: int = 5,
    *,
    use_cache: bool = True,
    http_client: Optional[httpx.AsyncClient] = None,
) -> List[Source]:
    """Fetch and process multiple candidates concurrently with a bounded semaphore."""
    semaphore = asyncio.Semaphore(max_concurrency)

    async def _fetch_single(cand: SearchResult | str, idx: int) -> Source:
        source_id = f"S{idx + 1}"
        async with semaphore:
            return await build_source(
                candidate=cand,
                source_id=source_id,
                entity=entity,
                use_cache=use_cache,
                http_client=http_client,
            )

    tasks = [_fetch_single(c, i) for i, c in enumerate(candidates)]
    return await asyncio.gather(*tasks)
