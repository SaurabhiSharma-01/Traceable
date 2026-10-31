"""
api/sources.py — Fast, thin endpoints for candidate search, batch fetching, and PDF upload.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from ..models import ExpectedTopic, Source
from ..pipeline.classify import classify_source, extract_domain
from ..pipeline.errors import SearchConfigError, SearchUnavailableError
from ..pipeline.fetch_clean import (
    build_source,
    fetch_sources_in_parallel,
    source_from_pdf,
    source_from_text,
)
from ..pipeline.source_acquisition import collect_candidates

logger = logging.getLogger("traceable.api.sources")

router = APIRouter(prefix="/api", tags=["sources"])


# ---------------------------------------------------------------------------
# Request & Response Schemas
# ---------------------------------------------------------------------------

class LightweightCandidate(BaseModel):
    url: str
    title: str
    domain: str
    source_class: str
    snippet: Optional[str] = None
    published_date: Optional[str] = None


class SearchSourcesRequestBody(BaseModel):
    entity: str
    topics: List[ExpectedTopic] = Field(default_factory=list)
    extra_urls: List[str] = Field(default_factory=list)
    max_sources: int = Field(default=8, ge=1, le=20)


class SearchSourcesResponseBody(BaseModel):
    candidates: List[LightweightCandidate]
    warnings: List[str] = Field(default_factory=list)


class FetchItem(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
    title: Optional[str] = None


class FetchSourcesRequestBody(BaseModel):
    entity: str = ""
    items: List[FetchItem] = Field(..., max_length=12)


class FetchSourcesResponseBody(BaseModel):
    sources: List[Source]
    warnings: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/sources/search",
    response_model=SearchSourcesResponseBody,
    summary="Search for candidate sources without fetching full pages",
)
async def api_search_sources(payload: SearchSourcesRequestBody):
    """Generate search queries and collect lightweight candidate sources."""
    try:
        collect_res = await collect_candidates(
            entity=payload.entity,
            topics=payload.topics,
            extra_urls=payload.extra_urls,
            max_sources=payload.max_sources,
        )

        candidates: list[LightweightCandidate] = []
        for cand in collect_res.candidates:
            domain = extract_domain(cand.url)
            s_class = classify_source(cand.url, title=cand.title, entity=payload.entity)
            candidates.append(
                LightweightCandidate(
                    url=cand.url,
                    title=cand.title,
                    domain=domain,
                    source_class=s_class,
                    snippet=cand.snippet,
                    published_date=cand.published_date,
                )
            )

        return SearchSourcesResponseBody(
            candidates=candidates,
            warnings=collect_res.warnings,
        )

    except SearchConfigError as sce:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(sce),
        ) from sce
    except SearchUnavailableError as sue:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(sue),
        ) from sue
    except Exception as exc:
        logger.exception("Unexpected error during sources search")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Candidate collection failed: {exc}",
        ) from exc


@router.post(
    "/sources/fetch",
    response_model=FetchSourcesResponseBody,
    summary="Fetch, clean, date, classify, and chunk URLs or pasted texts",
)
async def api_fetch_sources(payload: FetchSourcesRequestBody):
    """Process a batch of source items (URLs or pasted text) into chunked Sources."""
    sources: list[Source] = []
    warnings: list[str] = []

    # Separate URLs for parallel fetch from pasted text items
    url_items: list[tuple[int, str]] = []
    text_items: list[tuple[int, str, str]] = []

    for idx, item in enumerate(payload.items):
        if item.url and item.url.strip():
            url_items.append((idx, item.url.strip()))
        elif item.text and item.text.strip():
            text_items.append((idx, item.text.strip(), item.title or f"Pasted Text {idx+1}"))
        else:
            warnings.append(f"Item #{idx+1} had neither URL nor text; skipped.")

    # Fetch URLs in parallel
    if url_items:
        candidate_urls = [u for _, u in url_items]
        fetched_sources = await fetch_sources_in_parallel(
            candidates=candidate_urls,
            entity=payload.entity,
            max_concurrency=5,
        )
        for (idx, _), src in zip(url_items, fetched_sources):
            src.id = f"S{idx+1}"
            sources.append(src)

    # Process pasted texts
    for idx, raw_txt, title in text_items:
        src = await source_from_text(raw_txt, title, source_id=f"S{idx+1}")
        sources.append(src)

    # Sort sources back by original item order
    sources.sort(key=lambda s: int(s.id[1:]) if s.id.startswith("S") and s.id[1:].isdigit() else 999)

    return FetchSourcesResponseBody(sources=sources, warnings=warnings)


@router.post(
    "/pdf",
    response_model=Source,
    summary="Upload a PDF file and return cleaned, chunked Source",
)
async def api_upload_pdf(file: UploadFile = File(...)):
    """Accept an uploaded PDF document and extract clean text and passages."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF (.pdf) documents are accepted at this endpoint.",
        )

    try:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:  # 10 MB limit for upload
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="PDF file exceeds maximum allowed size of 10 MB.",
            )

        source = await source_from_pdf(
            data=content,
            filename=file.filename,
            source_id="S_upload",
        )
        return source

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("PDF upload processing failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process PDF file: {exc}",
        ) from exc

