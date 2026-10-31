"""
errors.py — Custom exception hierarchy for the LLM provider layer.

All LLM errors inherit from LLMError.
"""
from __future__ import annotations


class LLMError(Exception):
    """Base exception for all LLM-related failures."""
    pass


class LLMConfigError(LLMError):
    """Raised on configuration/authentication failures (e.g. missing/invalid API key, unsupported provider).

    These errors should NOT be retried.
    """
    pass


class LLMUnavailableError(LLMError):
    """Raised when the LLM service is unavailable (rate limits, 5xx server errors, timeouts)

    after all retry attempts have been exhausted.
    """
    pass


class LLMOutputError(LLMError):
    """Raised when the model's output cannot be parsed or validated against the requested schema

    even after a repair retry.
    """
    pass

