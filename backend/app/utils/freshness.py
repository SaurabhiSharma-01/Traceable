from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional


def compute_freshness(
    published_date: Optional[datetime],
    cycle_year: Optional[int],
    stale_months: int,
) -> Literal["fresh", "stale", "undated"]:
    """
    Determine whether a source is fresh, stale, or undated.

    Rules:
    - If no published_date: return "undated".
    - If published_date is older than stale_months from now: return "stale".
    - If cycle_year is provided and is more than 1 year behind current year: return "stale".
    - Otherwise: return "fresh".
    """
    if published_date is None:
        return "undated"

    now = datetime.utcnow()
    delta_months = (now.year - published_date.year) * 12 + (now.month - published_date.month)

    if delta_months > stale_months:
        return "stale"

    if cycle_year is not None:
        if now.year - cycle_year > 1:
            return "stale"

    return "fresh"
