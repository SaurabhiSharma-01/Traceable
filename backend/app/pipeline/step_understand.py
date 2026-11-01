"""
step_understand.py — Pipeline step for question understanding (delegates to query_understanding.py).
"""
from __future__ import annotations

from .query_understanding import UnderstandingResult, understand

__all__ = ["understand", "UnderstandingResult"]
