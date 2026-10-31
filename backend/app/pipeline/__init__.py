"""
app.pipeline — Source acquisition, query generation, fetching, dates, and chunking.
"""
from .chunking import chunk_text
from .classify import classify_source, extract_domain, is_primary_candidate
from .date_extraction import (
    extract_cycle_year,
    extract_published_date,
    freshness_status,
)
from .errors import (
    FetchError,
    PipelineError,
    SearchConfigError,
    SearchError,
    SearchUnavailableError,
    SSRFBlockedError,
)
from .fetch_clean import (
    build_source,
    fetch_sources_in_parallel,
    source_from_pdf,
    source_from_text,
    validate_url_safety,
)
from .queries import generate_queries
from .search import SearchProvider, SearchResult, TavilySearchProvider, search
from .source_acquisition import collect_candidates, normalize_url

__all__ = [
    "chunk_text",
    "classify_source",
    "extract_domain",
    "is_primary_candidate",
    "extract_published_date",
    "extract_cycle_year",
    "freshness_status",
    "PipelineError",
    "SearchError",
    "SearchConfigError",
    "SearchUnavailableError",
    "FetchError",
    "SSRFBlockedError",
    "build_source",
    "fetch_sources_in_parallel",
    "source_from_pdf",
    "source_from_text",
    "validate_url_safety",
    "generate_queries",
    "SearchProvider",
    "SearchResult",
    "TavilySearchProvider",
    "search",
    "collect_candidates",
    "normalize_url",
]
