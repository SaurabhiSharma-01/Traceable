"""
api/understand.py — Query understanding endpoint.
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from ..llm.errors import LLMConfigError, LLMOutputError, LLMUnavailableError
from ..pipeline.query_understanding import UnderstandingResult, understand

logger = logging.getLogger("traceable.api.understand")

router = APIRouter(prefix="/api", tags=["understand"])


class UnderstandRequestBody(BaseModel):
    question: str = Field(..., description="The user's research question (3-500 chars)")

    @field_validator("question")
    @classmethod
    def validate_question_length(cls, v: str) -> str:
        trimmed = v.strip()
        if len(trimmed) < 3:
            raise ValueError("Question must be at least 3 characters long.")
        if len(trimmed) > 500:
            raise ValueError("Question must not exceed 500 characters.")
        return trimmed


@router.post(
    "/understand",
    response_model=UnderstandingResult,
    summary="Understand a research question, identify entity, and generate expected verification topics",
)
async def api_understand(payload: UnderstandRequestBody):
    """Analyze a research question and return the target entity and 6-10 expected topics."""
    try:
        result = await understand(payload.question)
        return result

    except LLMConfigError as ce:
        logger.error("LLM config failure: %s", ce)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"error": "llm_config", "message": str(ce)},
        )
    except LLMUnavailableError as ue:
        logger.warning("LLM service unavailable: %s", ue)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "error": "llm_unavailable",
                "message": "The AI service is busy or unreachable. Try again shortly.",
            },
        )
    except LLMOutputError as oe:
        logger.warning("LLM output error: %s", oe)
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"error": "llm_output", "message": str(oe)},
        )
    except Exception as exc:
        logger.exception("Unexpected error in /api/understand")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "internal_error", "message": f"Query understanding failed: {exc}"},
        )

