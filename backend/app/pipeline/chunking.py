"""
chunking.py — Deterministic chunking of source text into stable passages.

Passage IDs follow format: S{source_id}-P{order} (e.g. S1-P0, S2-P5).
Preserves exact original wording so verbatim quote verification succeeds.
NO LLM is used in this module.
"""
from __future__ import annotations

import re
from typing import List

from ..models import Passage


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences while preserving exact character content."""
    # Split on sentence terminals followed by space, without discarding punctuation
    raw_sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in raw_sentences if s.strip()]


def _count_words(text: str) -> int:
    return len(text.split())


def chunk_text(
    text: str,
    source_id: str,
    target_words: int = 300,
    max_words: int = 400,
    title: str = "",
) -> List[Passage]:
    """Chunk clean text into stable, bounded Passages.

    Rules:
    - Splits on paragraph boundaries.
    - Merges consecutive short paragraphs until approaching target_words.
    - Splits overlong paragraphs on sentence boundaries.
    - Stable IDs: S{source_id}-P{order}
    - Exact original wording is preserved.
    """
    clean_text = text.strip()
    if not clean_text:
        return []

    # Clean source identifier: if source_id is already "S1", keep it; else format as S{source_id}
    clean_sid = source_id if source_id.startswith("S") else f"S{source_id}"

    # Split into paragraphs
    raw_paras = [p.strip() for p in re.split(r"\n\s*\n|\r\n\s*\r\n", clean_text) if p.strip()]
    if not raw_paras:
        raw_paras = [p.strip() for p in clean_text.splitlines() if p.strip()]

    # Normalize paragraph fragments
    normalized_paras: list[str] = []
    for para in raw_paras:
        w_count = _count_words(para)
        if w_count <= max_words:
            normalized_paras.append(para)
        else:
            # Paragraph exceeds max_words — split into sentences
            sentences = _split_into_sentences(para)
            current_chunk: list[str] = []
            current_words = 0
            for s in sentences:
                s_words = _count_words(s)
                if current_words + s_words > max_words and current_chunk:
                    normalized_paras.append(" ".join(current_chunk))
                    current_chunk = [s]
                    current_words = s_words
                else:
                    current_chunk.append(s)
                    current_words += s_words
            if current_chunk:
                normalized_paras.append(" ".join(current_chunk))

    # Merge short paragraphs up to target_words
    chunks: list[str] = []
    buffer: list[str] = []
    buffer_words = 0

    for para in normalized_paras:
        p_words = _count_words(para)
        if buffer_words + p_words <= target_words:
            buffer.append(para)
            buffer_words += p_words
        else:
            if buffer:
                chunks.append("\n\n".join(buffer))
            buffer = [para]
            buffer_words = p_words

    if buffer:
        chunks.append("\n\n".join(buffer))

    # Convert chunks to Passage objects with stable IDs
    passages: list[Passage] = []
    order = 0

    # Optional: include title as P0 if useful and not already at start of first chunk
    if title and title.strip():
        first_chunk_text = chunks[0] if chunks else ""
        if title.strip().lower() not in first_chunk_text.lower():
            passages.append(
                Passage(
                    id=f"{clean_sid}-P0",
                    source_id=source_id,
                    text=f"Title: {title.strip()}",
                    order=0,
                )
            )
            order = 1

    for chunk in chunks:
        pid = f"{clean_sid}-P{order}"
        passages.append(
            Passage(
                id=pid,
                source_id=source_id,
                text=chunk,
                order=order,
            )
        )
        order += 1

    return passages

