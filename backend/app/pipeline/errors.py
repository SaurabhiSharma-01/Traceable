"""
errors.py — Pipeline error hierarchy for search, fetch, and acquisition stages.
"""
from __future__ import annotations


class PipelineError(Exception):
    """Base error for all pipeline operations."""
    pass


class SearchError(PipelineError):
    """Base error for search operations."""
    pass


class SearchConfigError(SearchError):
    """Raised when search credentials are missing, rejected (401/403), or invalid.

    These errors should NOT be retried.
    """
    pass


class SearchUnavailableError(SearchError):
    """Raised when search service is rate-limited (429), unavailable (5xx),

    or timed out after all retries are exhausted.
    """
    pass


class FetchError(PipelineError):
    """Base error for source fetching failures."""
    pass


class SSRFBlockedError(FetchError):
    """Raised when an attempt to fetch an internal, loopback, or private IP is blocked."""
    pass

