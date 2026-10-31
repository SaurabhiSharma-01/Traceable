from __future__ import annotations

import re
from typing import Optional

from ..models import Passage


def chunk_text(
    text: str,
    source_id: str,
    max_words: int = 150,
) -> list[Passage]:
    """
    Split text into Passage objects.

    Strategy:
    1. Split on double newlines into paragraphs.
    2. If a paragraph exceeds max_words, split further on sentence boundaries.
    3. Assign stable IDs of the form S{source_id}-P{n}.
    """
    if not text or not text.strip():
        return []

    # Attempt to extract a numeric suffix from source_id for shorter IDs
    match = re.search(r"(\d+)$", source_id)
    id_part = match.group(1) if match else source_id

    raw_blocks = re.split(r"\n{2,}", text)

    chunks: list[str] = []
    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        words = block.split()
        if len(words) <= max_words:
            chunks.append(block)
        else:
            # Split on sentence boundaries
            sentences = re.split(r"(?<=[.!?])\s+", block)
            current: list[str] = []
            current_count = 0
            for sentence in sentences:
                s_words = sentence.split()
                if current_count + len(s_words) > max_words and current:
                    chunks.append(" ".join(current))
                    current = []
                    current_count = 0
                current.extend(s_words)
                current_count += len(s_words)
            if current:
                chunks.append(" ".join(current))

    passages: list[Passage] = []
    for n, chunk_text_content in enumerate(chunks):
        if not chunk_text_content.strip():
            continue
        passage = Passage(
            id=f"S{id_part}-P{n}",
            source_id=source_id,
            text=chunk_text_content.strip(),
            order=n,
        )
        passages.append(passage)

    return passages
