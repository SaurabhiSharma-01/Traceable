from __future__ import annotations

import logging
from typing import Optional

from pydantic import BaseModel

from ..llm.provider import LLMProvider
from ..models import ExpectedTopic, UnderstandResponse

logger = logging.getLogger(__name__)


# Internal LLM output schema
class _TopicItem(BaseModel):
    key: str
    label: str
    importance: int
    description: str


class _UnderstandLLMOutput(BaseModel):
    entity: str
    expected_topics: list[_TopicItem]


_UNDERSTAND_PROMPT = """You are an expert research analyst helping verify information quality.

A user has submitted this research question:
"{question}"

Your task:
1. Identify the PRIMARY ENTITY being researched (e.g., a scheme name, organization, program, person, policy).
2. Generate between 6 and 10 EXPECTED TOPICS that a thorough fact-checker would want to verify for this entity.

Guidelines for expected topics:
- Each topic should be a specific, verifiable claim or data point (e.g., eligibility criteria, application deadline, funding amount, official issuing authority).
- Assign an importance score from 1 (minor detail) to 5 (critical for the user's decision).
- The key must be a short snake_case identifier (e.g., "eligibility_criteria", "application_deadline").
- The description must explain what information to look for and why it matters.
- Do NOT fabricate specific values — identify what SHOULD be checked, not the answer itself.
- Use ONLY the provided question text. Do not use external knowledge about the entity.

Return JSON only. No markdown fences. No commentary.

{{
  "entity": "<name of the primary entity>",
  "expected_topics": [
    {{
      "key": "topic_key",
      "label": "Human-readable topic name",
      "importance": 1-5,
      "description": "What to verify and why it matters"
    }}
  ]
}}"""


async def run(question: str, llm: LLMProvider) -> UnderstandResponse:
    """
    Identify the entity and expected topics for a research question.
    """
    prompt = _UNDERSTAND_PROMPT.format(question=question)
    result: _UnderstandLLMOutput = await llm.complete(prompt, _UnderstandLLMOutput)

    topics = [
        ExpectedTopic(
            key=t.key,
            label=t.label,
            importance=max(1, min(5, t.importance)),
            description=t.description,
        )
        for t in result.expected_topics
    ]

    return UnderstandResponse(entity=result.entity, expected_topics=topics)
