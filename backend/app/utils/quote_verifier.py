from __future__ import annotations

from typing import Optional

from rapidfuzz import fuzz


def verify_quote(quote: Optional[str], passage_text: str) -> bool:
    """
    Exact substring verification.

    Returns True iff quote is not None and quote.strip() is a substring of
    passage_text.
    """
    if quote is None:
        return False
    return quote.strip() in passage_text


def fuzzy_verify(
    quote: Optional[str], passage_text: str, threshold: int = 90
) -> bool:
    """
    Fuzzy verification using rapidfuzz partial_ratio.

    Returns True iff the partial ratio between quote and passage_text meets
    or exceeds the threshold.
    """
    if quote is None:
        return False
    score = fuzz.partial_ratio(quote.strip(), passage_text)
    return score >= threshold
