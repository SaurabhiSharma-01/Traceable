"""
query_understanding.py — Query understanding pipeline module (Module A).

Extracts the target entity, classifies intent and entity type, and generates 6-10
structured expected verification topics using Gemini structured outputs.
"""
from __future__ import annotations

import logging
import re
from typing import List, Optional

from pydantic import BaseModel, Field

from ..llm.errors import LLMOutputError
from ..llm.prompts import QUERY_UNDERSTANDING_SYSTEM, QUERY_UNDERSTANDING_USER_TEMPLATE
from ..llm.provider import generate_json
from ..models import ExpectedTopic

logger = logging.getLogger("traceable.understanding")

YEAR_OR_CURRENCY_PATTERN = re.compile(
    r"\b(19\d\d|20\d\d)\b|"               # 4-digit years (1900-2099)
    r"[$€£₹]|"                            # Currency symbols
    r"\b(rs\.?|inr|usd|eur|gbp)\b\s*\d+|" # Currency codes with digits
    r"\b\d+\s*(lakh|crore|thousand|million|billion)\b|" # Denominated numbers
    r"\b(rupees|dollars|cents)\b",
    re.IGNORECASE,
)


def has_year_or_currency(text: str) -> bool:
    """Return True if text contains a 4-digit year or currency amount."""
    return bool(YEAR_OR_CURRENCY_PATTERN.search(text))


class UnderstandingResult(BaseModel):
    """Structured understanding of the user's research question."""
    entity: Optional[str] = None
    entity_type: Optional[str] = None  # short human phrase with spaces, e.g. "government scholarship scheme"
    intent: str                        # short human phrase with spaces, e.g. "verify before applying"
    expected_topics: List[ExpectedTopic] = Field(default_factory=list)
    ambiguity_note: Optional[str] = None
    needs_clarification: bool = False
    clarification_question: Optional[str] = None


def _to_snake_case(key_str: str) -> str:
    """Normalize a topic key into clean English snake_case."""
    # Replace non-alphanumeric with underscore
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", key_str.strip().lower())
    # Remove leading/trailing underscores and duplicate underscores
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned or "topic"


def post_process_understanding(raw: UnderstandingResult) -> UnderstandingResult:
    """Deterministic post-processing of query understanding result.

    Rules:
    - Deduplicates keys, forces snake_case, clamps importance to 1-5.
    - Replaces internal newlines/tabs in topic descriptions and labels with single spaces.
    - Normalizes entity_type and intent into human-readable phrases with spaces (no snake_case).
    - ambiguity_note must not name sub-schemes or categories from memory.
    - Rejects / strips 4-digit years and currency amounts from topic descriptions.
    - Caps list at 10 and drops empty topics.
    - If needs_clarification is True, topics are not required.
    - If fewer than 5 valid topics remain, raises LLMOutputError.
    - Trims whitespace and caps entity length at 150 characters.
    """
    # 1. Clean entity
    clean_entity = None
    if raw.entity and raw.entity.strip():
        clean_entity = raw.entity.strip()[:150]

    # Human-readable entity_type and intent (with spaces, not snake_case)
    clean_entity_type = " ".join((raw.entity_type or "other").replace("_", " ").split())
    clean_intent = " ".join((raw.intent or "pre-application verification").replace("_", " ").split())

    # ambiguity_note hygiene
    clean_ambiguity: Optional[str] = None
    if raw.ambiguity_note and raw.ambiguity_note.strip():
        note_str = " ".join(raw.ambiguity_note.split())
        # Rule: ambiguity_note must not name sub-schemes or categories from memory.
        # It may only say that the name may refer to several programs or components.
        if "refer to several programs" in note_str.lower() or "confirm which" in note_str.lower():
            clean_ambiguity = note_str
        else:
            clean_ambiguity = "This name may refer to several programs or components; confirm which one applies."

    # 2. If clarification is needed, return without topic requirement
    if raw.needs_clarification:
        return UnderstandingResult(
            entity=clean_entity,
            entity_type=clean_entity_type if raw.entity_type else None,
            intent=clean_intent,
            expected_topics=[],
            ambiguity_note=clean_ambiguity,
            needs_clarification=True,
            clarification_question=raw.clarification_question.strip() if raw.clarification_question else "Which specific program or scheme would you like to verify?",
        )

    # 3. Clean and deduplicate topics
    seen_keys = set()
    cleaned_topics: list[ExpectedTopic] = []

    for t in raw.expected_topics:
        # Replace newlines, tabs, multiple spaces with single space
        lbl = " ".join((t.label or "").split())
        desc = " ".join((t.description or "").split())
        raw_key = t.key or lbl

        clean_key = _to_snake_case(raw_key)

        # Drop empty topics
        if not lbl and not desc:
            continue
        if not lbl:
            lbl = clean_key.replace("_", " ").title()

        # Sanitize descriptions containing 4-digit years or currency amounts
        if has_year_or_currency(desc):
            sanitized_desc = YEAR_OR_CURRENCY_PATTERN.sub("", desc).strip()
            desc = " ".join(sanitized_desc.split())
            if not desc:
                desc = f"Verify {lbl.lower()} in official sources"

        # Clamp importance to 1-5
        try:
            imp = max(1, min(5, int(t.importance)))
        except (ValueError, TypeError):
            imp = 3

        if clean_key not in seen_keys:
            seen_keys.add(clean_key)
            cleaned_topics.append(
                ExpectedTopic(
                    key=clean_key,
                    label=lbl,
                    importance=imp,
                    description=desc,
                    is_critical=bool(t.is_critical),
                )
            )

        if len(cleaned_topics) >= 10:
            break

    # 4. Enforce minimum topics threshold
    if len(cleaned_topics) < 5:
        raise LLMOutputError(
            f"Fewer than 5 valid expected topics were produced (got {len(cleaned_topics)}). Complete verification requires at least 5 topics."
        )

    return UnderstandingResult(
        entity=clean_entity,
        entity_type=clean_entity_type,
        intent=clean_intent,
        expected_topics=cleaned_topics,
        ambiguity_note=clean_ambiguity,
        needs_clarification=False,
        clarification_question=None,
    )


async def understand(question: str) -> UnderstandingResult:
    """Understand a research question using Gemini structured outputs."""
    clean_q = question.strip()
    if not clean_q:
        return UnderstandingResult(
            entity=None,
            entity_type=None,
            intent="unknown",
            expected_topics=[],
            needs_clarification=True,
            clarification_question="Please enter a research question or scheme name to verify.",
        )

    prompt = QUERY_UNDERSTANDING_USER_TEMPLATE.format(question=clean_q)

    # Call LLM provider layer
    raw_result = await generate_json(
        prompt=prompt,
        schema=UnderstandingResult,
        system=QUERY_UNDERSTANDING_SYSTEM,
        cache=True,
        task="understanding",
    )

    # Post-check: reject descriptions containing 4-digit years or currency amounts, and re-prompt once
    if not raw_result.needs_clarification and raw_result.expected_topics:
        offending = [
            t for t in raw_result.expected_topics
            if has_year_or_currency(t.description or "")
        ]
        if offending:
            logger.warning(
                "[Understanding] Detected 4-digit year or currency in %d topic descriptions. Re-prompting once...",
                len(offending),
            )
            offending_str = "\n".join(f"- {t.key}: {t.description}" for t in offending)
            repair_prompt = (
                f"{prompt}\n\n"
                f"CORRECTION REQUIRED: Your previous output included specific dates, years, or currency amounts:\n"
                f"{offending_str}\n"
                f"RULE VIOLATION: Topic descriptions MUST be purely generic 'what to check' statements without any 4-digit years or currency amounts.\n"
                f"Please regenerate the structured output ensuring all descriptions are strictly generic."
            )
            try:
                repaired_result = await generate_json(
                    prompt=repair_prompt,
                    schema=UnderstandingResult,
                    system=QUERY_UNDERSTANDING_SYSTEM,
                    cache=False,
                    task="understanding_hygiene_repair",
                )
                raw_result = repaired_result
            except Exception as rep_err:
                logger.warning(
                    "[Understanding] Hygiene re-prompt failed (%s); proceeding with post-processing sanitization.",
                    rep_err,
                )

    return post_process_understanding(raw_result)

