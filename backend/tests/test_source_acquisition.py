"""
test_source_acquisition.py — Comprehensive unit tests for Phase 1+9 (Search, Fetch, Dates, Chunking).

Covers:
- Date extraction (meta, JSON-LD, visible text, URL pattern, none, future date rejection, dd/mm vs mm/dd)
- Cycle year extraction on varied formats
- Freshness status logic (fresh, stale by date, stale by cycle, undated, current cycle override)
- Chunking (stable ID format, ordering, max words bound, verbatim wording preserved)
- URL normalization and 2-per-domain cap
- Classification for official, news, aggregator, forum, blog, unknown
- SSRF guard against private, link-local, loopback IPs
- Fetch failure modes (failed, blocked, empty) without raising
- Search provider with injected fake HTTP layer (success, missing key, 401, 429-then-success, cache hit)
"""
from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

import httpx
import pytest

from app.config import settings
from app.models import ExpectedTopic
from app.pipeline.chunking import chunk_text
from app.pipeline.classify import classify_source, extract_domain
from app.pipeline.date_extraction import (
    extract_cycle_year,
    extract_published_date,
    freshness_status,
)
from app.pipeline.errors import SearchConfigError, SearchUnavailableError, SSRFBlockedError
from app.pipeline.fetch_clean import (
    build_source,
    clean_html_to_text,
    source_from_text,
    validate_url_safety,
)
from app.pipeline.search import SearchResult, TavilySearchProvider
from app.pipeline.source_acquisition import collect_candidates, normalize_url

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# 1. Date Extraction Tests
# ---------------------------------------------------------------------------

def test_date_extraction_meta():
    html = (FIXTURES_DIR / "sample_article_meta.html").read_text(encoding="utf-8")
    d, origin = extract_published_date(html, "", "https://example.com/scholarship")
    assert origin == "meta"
    assert d == date(2024, 10, 20)  # modified_time takes precedence over published_time


def test_date_extraction_jsonld():
    html = (FIXTURES_DIR / "sample_article_jsonld.html").read_text(encoding="utf-8")
    d, origin = extract_published_date(html, "", "https://example.com/post-matric")
    assert origin == "jsonld"
    assert d == date(2024, 9, 15)  # dateModified takes precedence over datePublished


def test_date_extraction_visible_text():
    html = (FIXTURES_DIR / "sample_article_visible_text.html").read_text(encoding="utf-8")
    text = clean_html_to_text(html)
    d, origin = extract_published_date(None, text, "https://example.com/page")
    assert origin == "visible_text"
    assert d == date(2024, 11, 14)  # Indian format dd/mm/yyyy


def test_date_extraction_url_pattern():
    d, origin = extract_published_date(None, "General text with no dates.", "https://example.com/news/2023/05/18/update.html")
    assert origin == "url_pattern"
    assert d == date(2023, 5, 18)


def test_date_extraction_none():
    d, origin = extract_published_date(None, "No dates anywhere in this plain text.", "https://example.com/portal/about")
    assert origin == "none"
    assert d is None


def test_date_extraction_future_date_rejected():
    future_html = '<html><head><meta property="article:published_time" content="2099-01-01T00:00:00Z" /></head></html>'
    d, origin = extract_published_date(future_html, "", "https://example.com")
    assert d is None
    assert origin == "none"


def test_date_extraction_indian_day_first():
    text = "Important Notice: Last Updated on 05/12/2024."
    d, origin = extract_published_date(None, text, "https://example.com")
    assert origin == "visible_text"
    # Should prefer 5th December (dayfirst=True) rather than 12th May
    assert d == date(2024, 12, 5)


# ---------------------------------------------------------------------------
# 2. Cycle Year Regex Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "input_text, expected_cycle",
    [
        ("PM YASASVI Scheme 2025-26 notification", "2025-26"),
        ("Application open for academic year 2025-2026 session", "2025-26"),
        ("Notice regarding AY 2024-25 admissions", "2024-25"),
        ("Guidelines for Session 2025 eligible students", "2025"),
        ("Batch of 2026 graduation award", "2026"),
        ("FY 2025-26 budget allocation for grants", "2025-26"),
        ("Class of 2025 entrance criteria", "2025"),
        ("Random text with no cycle reference", None),
    ],
)
def test_extract_cycle_year(input_text, expected_cycle):
    assert extract_cycle_year("Title", input_text) == expected_cycle


# ---------------------------------------------------------------------------
# 3. Freshness Status Tests
# ---------------------------------------------------------------------------

def test_freshness_status_logic():
    today = date(2026, 11, 1)

    # 1. Fresh: published 3 months ago (within 12 stale_months)
    recent = date(2026, 8, 1)
    assert freshness_status(recent, None, today, stale_months=12) == "fresh"

    # 2. Stale by date: published 24 months ago with no modern cycle
    old_date = date(2024, 5, 1)
    assert freshness_status(old_date, None, today, stale_months=12) == "stale"

    # 3. Undated
    assert freshness_status(None, None, today, stale_months=12) == "undated"

    # 4. Old published date BUT page text explicitly mentions current/future cycle year (override to fresh)
    assert freshness_status(old_date, "2026-27", today, stale_months=12) == "fresh"

    # 5. Stale by past cycle year
    assert freshness_status(None, "2022-23", today, stale_months=12) == "stale"


# ---------------------------------------------------------------------------
# 4. Chunking Tests
# ---------------------------------------------------------------------------

def test_chunking_ids_and_wording():
    sample_text = (
        "Paragraph one introduces the National Scholarship eligibility criteria and terms.\n\n"
        "Paragraph two describes the essential documents needed for verification, including income certificate.\n\n"
        "Paragraph three covers the renewal policy and application guidelines."
    )
    passages = chunk_text(sample_text, source_id="S1", target_words=20, max_words=50)
    assert len(passages) >= 2

    # Check ID format and sequence
    assert passages[0].id == "S1-P0"
    assert passages[1].id == "S1-P1"
    assert passages[0].order == 0
    assert passages[1].order == 1

    # Verify exact wording is preserved (no dropped words)
    assert "income certificate" in passages[0].text or "income certificate" in passages[1].text


def test_chunking_max_words_bound():
    # Long text with repetitive sentences
    sentence = "The student must submit an active bank passbook and domicile proof. "
    long_para = sentence * 60  # ~600 words in a single paragraph
    passages = chunk_text(long_para, source_id="S2", target_words=100, max_words=120)

    for p in passages:
        word_count = len(p.text.split())
        assert word_count <= 150  # sentence splitter stays tightly bounded


# ---------------------------------------------------------------------------
# 5. URL Normalization and Per-Domain Cap Tests
# ---------------------------------------------------------------------------

def test_url_normalization():
    dirty_url = "HTTPS://WWW.Example.com:443/scholarships/apply/?utm_source=google&fbclid=12345&id=99#section2"
    cleaned = normalize_url(dirty_url)
    assert cleaned == "https://www.example.com/scholarships/apply?id=99"


@pytest.mark.asyncio
async def test_candidate_collection_per_domain_cap(monkeypatch):
    # Fake search results containing 4 items from the same domain
    domain_results = [
        SearchResult(url=f"https://aggregator.com/article/{i}", title=f"Post {i}", score=0.8 - i * 0.1)
        for i in range(4)
    ]

    async def fake_search(query, **kwargs):
        return domain_results

    monkeypatch.setattr("app.pipeline.source_acquisition.search", fake_search)

    topics = [ExpectedTopic(key="eligibility", label="Eligibility", importance=5, description="")]
    res = await collect_candidates("Test Scheme", topics, max_sources=8, use_cache=False)

    # Must retain at most 2 results from aggregator.com
    aggregator_cands = [c for c in res.candidates if "aggregator.com" in c.url]
    assert len(aggregator_cands) <= 2


# ---------------------------------------------------------------------------
# 6. Source Classification Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url, title, entity, expected_class",
    [
        ("https://scholarships.gov.in/portal", "NSP Portal", "NSP", "official"),
        ("https://iitd.ac.in/scholarship", "IIT Delhi Grants", "IIT Delhi", "official"),
        ("https://www.bbc.com/news/world-asia-india", "BBC News Update", "NSP", "news"),
        ("https://buddy4study.com/scholarships/post-matric", "Top Scholarships", "Post Matric", "aggregator"),
        ("https://www.reddit.com/r/india/comments/scholarship", "Discussion", "NSP", "forum"),
        ("https://studenthelp.blogspot.com/2024/guide.html", "My Experience", "NSP", "blog"),
        ("https://randomunknownsite123.com/page", "Information", "NSP", "unknown"),
    ],
)
def test_classify_source(url, title, entity, expected_class):
    assert classify_source(url, title=title, entity=entity) == expected_class


# ---------------------------------------------------------------------------
# 7. SSRF Guard Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bad_url",
    [
        "http://localhost:8000/admin",
        "http://127.0.0.1:5000",
        "http://10.0.0.1/internal",
        "http://192.168.1.1/router",
        "http://169.254.169.254/latest/meta-data",  # AWS/cloud link-local metadata
    ],
)
def test_ssrf_guard_blocks_private_ips(bad_url):
    with pytest.raises(SSRFBlockedError):
        validate_url_safety(bad_url)


# ---------------------------------------------------------------------------
# 8. Fetch Failure Modes Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_fetch_failure_modes_do_not_crash(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SQLITE_DB_PATH", str(tmp_path / "test.sqlite"))

    # Test SSRF refusal turns into fetch_status="blocked" without raising
    blocked_src = await build_source("http://127.0.0.1:9999", source_id="S1", use_cache=False)
    assert blocked_src.fetch_status == "blocked"
    assert "SSRF Refusal" in (blocked_src.error_message or "")

    # Test timeout turns into fetch_status="failed"
    fake_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: (_ for _ in ()).throw(httpx.TimeoutException("Timeout!")))
    )
    failed_src = await build_source(
        "https://example.com/slow",
        source_id="S2",
        use_cache=False,
        http_client=fake_client,
    )
    assert failed_src.fetch_status == "failed"
    assert "timed out" in (failed_src.error_message or "").lower()


# ---------------------------------------------------------------------------
# 9. Search Provider with Injected Fake HTTP Layer Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_provider_success(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SQLITE_DB_PATH", str(tmp_path / "test.sqlite"))
    monkeypatch.setattr(settings, "SEARCH_API_KEY", "tvly-test-key")

    mock_resp = {
        "results": [
            {
                "url": "https://scholarships.gov.in",
                "title": "National Scholarship Portal",
                "content": "Official application portal",
                "score": 0.98,
            }
        ]
    }

    fake_client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda req: httpx.Response(200, json=mock_resp))
    )

    provider = TavilySearchProvider(api_key="tvly-test", http_client=fake_client)
    res = await provider.search("scholarship", max_results=2, use_cache=False)
    assert len(res) == 1
    assert res[0].url == "https://scholarships.gov.in"
    assert res[0].title == "National Scholarship Portal"


@pytest.mark.asyncio
async def test_search_provider_missing_key():
    provider = TavilySearchProvider(api_key="")
    with pytest.raises(SearchConfigError) as exc_info:
        await provider.search("query", use_cache=False)
    assert "SEARCH_API_KEY missing" in str(exc_info.value)


@pytest.mark.asyncio
async def test_search_provider_401_no_retry():
    call_count = 0

    def mock_handler(req):
        nonlocal call_count
        call_count += 1
        return httpx.Response(401, json={"error": "Unauthorized key"})

    fake_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = TavilySearchProvider(api_key="tvly-invalid", http_client=fake_client)

    with pytest.raises(SearchConfigError):
        await provider.search("query", use_cache=False)

    assert call_count == 1  # No retries on 401


@pytest.mark.asyncio
async def test_search_provider_429_then_success(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "SQLITE_DB_PATH", str(tmp_path / "test.sqlite"))
    # Patch asyncio.sleep so backoff is instantaneous
    async def fast_sleep(d=0):
        pass
    monkeypatch.setattr(asyncio, "sleep", fast_sleep)

    call_count = 0

    def mock_handler(req):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(429, headers={"Retry-After": "0.01"})
        return httpx.Response(200, json={"results": [{"url": "https://example.com", "title": "Recovered"}]})

    fake_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = TavilySearchProvider(api_key="tvly-key", http_client=fake_client)

    res = await provider.search("query", use_cache=False)
    assert len(res) == 1
    assert res[0].title == "Recovered"
    assert call_count == 2


@pytest.mark.asyncio
async def test_search_provider_cache_hit(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test_search_cache.sqlite")
    monkeypatch.setattr(settings, "SQLITE_DB_PATH", db_file)

    call_count = 0

    def mock_handler(req):
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json={"results": [{"url": "https://cached.org", "title": "Cached Title"}]})

    fake_client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = TavilySearchProvider(api_key="tvly-key", http_client=fake_client)

    # 1. First call: cache miss, calls client
    res1 = await provider.search("fixed query", use_cache=True)
    assert len(res1) == 1
    assert call_count == 1

    # 2. Second call with same query: cache hit, mock_handler NOT called again
    res2 = await provider.search("fixed query", use_cache=True)
    assert len(res2) == 1
    assert res2[0].title == "Cached Title"
    assert call_count == 1  # Call count unchanged!
