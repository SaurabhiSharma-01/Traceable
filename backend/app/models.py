"""
models.py — All Pydantic v2 data models for Traceable.

These are the single source of truth for data shapes used across the backend.
The frontend TypeScript types in frontend/src/types.ts must mirror these exactly.

Section 8 of SPEC.md defines the contract — change both files together.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Core pipeline models
# ---------------------------------------------------------------------------

class Passage(BaseModel):
    """A chunked excerpt from a source, with a stable ID."""
    id: str                  # e.g. "S2-P5"
    source_id: str
    text: str
    order: int               # 0-based position within the source


class Source(BaseModel):
    """A web page, PDF, pasted text or search result that was collected."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: Literal["url", "text", "pdf", "search"]
    url: Optional[str] = None
    title: Optional[str] = None
    domain: Optional[str] = None
    source_class: Literal["official", "news", "aggregator", "blog", "forum", "unknown"] = "unknown"
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    published_date: Optional[datetime] = None
    date_origin: Literal["meta", "jsonld", "visible_text", "url_pattern", "none"] = "none"
    date_status: Literal["fresh", "stale", "undated"] = "undated"
    cycle_year: Optional[str | int] = None
    fetch_status: Literal["ok", "failed", "blocked", "empty"] = "ok"
    error_message: Optional[str] = None
    passages: list[Passage] = Field(default_factory=list)


class ExpectedTopic(BaseModel):
    """A topic the analysis is expected to find information about."""
    key: str                 # e.g. "eligibility_criteria"
    label: str               # Human-readable label, e.g. "Eligibility Criteria"
    importance: int = Field(default=3)  # clamped to 1-5 by clamp_importance validator
    description: str
    is_critical: bool = False

    @field_validator("importance", mode="before")
    @classmethod
    def clamp_importance(cls, v: Any) -> int:
        try:
            return max(1, min(5, int(v)))
        except (ValueError, TypeError):
            return 3


class Fact(BaseModel):
    """A single piece of extracted information from a source about a topic."""
    source_id: str
    topic_key: str
    found: bool              # False means "not found in this source"
    value: Optional[str] = None
    quote: Optional[str] = None      # Verbatim quote, max 40 words
    passage_id: Optional[str] = None
    cycle_year: Optional[str | int] = None
    confidence: Literal["low", "medium", "high"] = "low"
    quote_verified: bool = False     # True if quote is a substring of the passage


class EvidenceRef(BaseModel):
    """A reference to a specific passage quote that backs a finding."""
    source_id: str
    passage_id: Optional[str] = None
    quote: Optional[str] = None


class Finding(BaseModel):
    """A gap, conflict, freshness issue, risk signal, or summary finding."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    kind: Literal["summary", "gap", "conflict", "stale", "unanswered_question", "risk"]
    label: Literal["SOURCED", "POTENTIAL", "UNCERTAIN"]
    topic_key: Optional[str] = None
    title: str
    explanation: str
    evidence: list[EvidenceRef] = Field(default_factory=list)
    confidence: Optional[Literal["low", "medium", "high"]] = None
    evidence_level: Optional[
        Literal[
            "primary_supported",
            "corroborated",
            "single_origin",
            "contradicted_by_primary",
            "unsupported",
        ]
    ] = None
    independent_origins: Optional[int] = None
    priority_score: float = 0.0


class ChecklistItem(BaseModel):
    """An actionable verify-next item linked to one or more findings."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    priority_rank: int
    action: str
    reason: str
    linked_finding_ids: list[str] = Field(default_factory=list)
    suggested_official_source: Optional[str] = None
    status: Literal["todo", "done"] = "todo"


class Analysis(BaseModel):
    """The complete result of a Traceable research run."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    question: str
    entity: Optional[str] = None
    expected_topics: list[ExpectedTopic] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    facts: list[Fact] = Field(default_factory=list)
    # coverage_matrix[topic_key][source_id] = True if a verified fact was found
    coverage_matrix: dict[str, dict[str, bool]] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# API request / response models
# ---------------------------------------------------------------------------

class UnderstandRequest(BaseModel):
    question: str


class UnderstandResponse(BaseModel):
    entity: str
    expected_topics: list[ExpectedTopic]


class SearchSourcesRequest(BaseModel):
    entity: str
    topics: list[ExpectedTopic]
    max_results: int = 10


class FetchSourcesRequest(BaseModel):
    urls: list[str] = Field(default_factory=list)
    pasted_texts: list[str] = Field(default_factory=list)


class StartAnalysisRequest(BaseModel):
    question: str
    entity: str
    expected_topics: list[ExpectedTopic]
    source_ids: list[str]


class ProgressEvent(BaseModel):
    stage: str
    message: str
    percent: int
