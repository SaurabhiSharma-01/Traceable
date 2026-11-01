"""
test_query_understanding.py — Unit tests for Query Understanding (backend).

Covers:
- valid output passes post-processing
- duplicate and badly formatted keys are fixed
- importance clamped, list capped at 10
- fewer than 5 topics raises LLMOutputError
- entity=None with needs_clarification=True is returned without error
- endpoint returns 422 for empty or too-long questions
- endpoint maps LLMConfigError, LLMUnavailableError, LLMOutputError to the right status codes and messages
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.llm.errors import LLMConfigError, LLMOutputError, LLMUnavailableError
from app.llm.provider import reset_client, set_client
from app.main import app
from app.models import ExpectedTopic
from app.pipeline.query_understanding import (
    UnderstandingResult,
    post_process_understanding,
    understand,
)


class FakeResponse:
    def __init__(self, text: str, total_tokens: int = 50):
        self.text = text
        self.total_tokens = total_tokens


class FakeClient:
    def __init__(self, payload: Any):
        self.payload = payload
        self.call_count = 0

    async def generate_content(self, contents: str, schema: Any, system: str) -> FakeResponse:
        self.call_count += 1
        if isinstance(self.payload, Exception):
            raise self.payload
        if isinstance(self.payload, str):
            return FakeResponse(self.payload)
        return FakeResponse(json.dumps(self.payload))


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "SQLITE_DB_PATH", str(tmp_path / "test.sqlite"))
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "AQ.test_key")
    reset_client()
    yield
    reset_client()


def test_valid_output_post_processing():
    topics = [
        ExpectedTopic(key="eligibility_criteria", label="Eligibility Criteria", importance=5, description="Who can apply", is_critical=True),
        ExpectedTopic(key="application_deadline", label="Application Deadline", importance=5, description="Last date", is_critical=True),
        ExpectedTopic(key="required_documents", label="Required Documents", importance=4, description="Certificates needed", is_critical=True),
        ExpectedTopic(key="official_link", label="Official Link", importance=4, description="Portal URL", is_critical=False),
        ExpectedTopic(key="renewal_policy", label="Renewal Policy", importance=3, description="Yearly renewal terms", is_critical=False),
        ExpectedTopic(key="award_amount", label="Award Amount", importance=3, description="Financial benefit", is_critical=False),
    ]
    raw = UnderstandingResult(
        entity="PM YASASVI",
        entity_type="scholarship",
        intent="pre-application verification",
        expected_topics=topics,
        ambiguity_note=None,
        needs_clarification=False,
    )
    processed = post_process_understanding(raw)
    assert processed.entity == "PM YASASVI"
    assert len(processed.expected_topics) == 6
    assert processed.expected_topics[0].key == "eligibility_criteria"
    assert processed.expected_topics[0].is_critical is True


def test_duplicate_and_badly_formatted_keys_fixed():
    topics = [
        ExpectedTopic(key="  Eligibility Criteria!!  ", label="Eligibility", importance=5, description=""),
        ExpectedTopic(key="eligibility_criteria", label="Duplicate Key", importance=4, description=""),  # duplicate
        ExpectedTopic(key="APPLICATION DEADLINE 2025", label="Deadline", importance=5, description=""),
        ExpectedTopic(key="Required--Documents", label="Documents", importance=4, description=""),
        ExpectedTopic(key="how to apply", label="Process", importance=3, description=""),
        ExpectedTopic(key="official website link", label="Portal", importance=3, description=""),
    ]
    raw = UnderstandingResult(
        entity="NSP",
        intent="verification",
        expected_topics=topics,
    )
    processed = post_process_understanding(raw)
    keys = [t.key for t in processed.expected_topics]
    assert keys == [
        "eligibility_criteria",
        "application_deadline_2025",
        "required_documents",
        "how_to_apply",
        "official_website_link",
    ]
    assert len(keys) == 5


def test_importance_clamped_and_list_capped_at_10():
    # 12 topics with out-of-range importances (e.g. 10 and -3)
    topics = [
        ExpectedTopic(key=f"topic_{i}", label=f"Topic {i}", importance=10 if i % 2 == 0 else -3, description="desc")
        for i in range(12)
    ]
    raw = UnderstandingResult(
        entity="Test Entity",
        intent="intent",
        expected_topics=topics,
    )
    processed = post_process_understanding(raw)
    assert len(processed.expected_topics) == 10  # Capped at 10
    assert processed.expected_topics[0].importance == 5  # Clamped 10 -> 5
    assert processed.expected_topics[1].importance == 1  # Clamped -3 -> 1
    for t in processed.expected_topics:
        assert 1 <= t.importance <= 5  # Clamped to 1-5


def test_fewer_than_5_topics_raises_llm_output_error():
    topics = [
        ExpectedTopic(key="t1", label="Topic 1", importance=3, description="desc"),
        ExpectedTopic(key="t2", label="Topic 2", importance=3, description="desc"),
        ExpectedTopic(key="t3", label="Topic 3", importance=3, description="desc"),
    ]
    raw = UnderstandingResult(
        entity="Scheme",
        intent="intent",
        expected_topics=topics,
    )
    with pytest.raises(LLMOutputError) as exc_info:
        post_process_understanding(raw)
    assert "Fewer than 5 valid expected topics" in str(exc_info.value)


def test_needs_clarification_no_topics_required():
    raw = UnderstandingResult(
        entity=None,
        intent="general",
        expected_topics=[],
        needs_clarification=True,
        clarification_question="Which specific scholarship are you asking about?",
    )
    processed = post_process_understanding(raw)
    assert processed.needs_clarification is True
    assert processed.entity is None
    assert processed.expected_topics == []
    assert "Which specific scholarship" in (processed.clarification_question or "")


@pytest.mark.asyncio
async def test_endpoint_validation_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Too short (< 3 chars)
        res_short = await ac.post("/api/understand", json={"question": "hi"})
        assert res_short.status_code == 422

        # Too long (> 500 chars)
        res_long = await ac.post("/api/understand", json={"question": "x" * 501})
        assert res_long.status_code == 422

        # Empty body
        res_empty = await ac.post("/api/understand", json={})
        assert res_empty.status_code == 422


@pytest.mark.asyncio
async def test_endpoint_error_mappings():
    # 1. LLMConfigError -> 503
    fake_config_err = FakeClient(LLMConfigError("GEMINI_API_KEY missing or rejected"))
    set_client(fake_config_err)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/understand", json={"question": "Valid research question here"})
        assert res.status_code == 503
        data = res.json()
        assert data["error"] == "llm_config"

    # 2. LLMUnavailableError -> 503
    fake_unavail_err = FakeClient(LLMUnavailableError("All retries exhausted"))
    set_client(fake_unavail_err)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/understand", json={"question": "Valid research question here"})
        assert res.status_code == 503
        data = res.json()
        assert data["error"] == "llm_unavailable"
        assert "busy or unreachable" in data["message"]

    # 3. LLMOutputError -> 502
    fake_output_err = FakeClient(LLMOutputError("Validation failed"))
    set_client(fake_output_err)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.post("/api/understand", json={"question": "Valid research question here"})
        assert res.status_code == 502
        data = res.json()
        assert data["error"] == "llm_output"


def test_newlines_in_topic_description_and_labels_cleaned():
    """Verify topic descriptions with stray newlines are collapsed onto a single line."""
    topics = [
        ExpectedTopic(
            key="eligibility_criteria",
            label="Eligibility\nCriteria",
            importance=5,
            description="Verify household income thresholds.\nMust not exceed limits.",
            is_critical=True,
        ),
        ExpectedTopic(key="deadline", label="Deadline", importance=5, description="Last date for submission\r\nand review", is_critical=True),
        ExpectedTopic(key="docs", label="Documents", importance=4, description="Check certificates\nneeded", is_critical=True),
        ExpectedTopic(key="portal", label="Portal", importance=4, description="Official portal link", is_critical=False),
        ExpectedTopic(key="renewal", label="Renewal", importance=3, description="Renewal policy", is_critical=False),
    ]
    raw = UnderstandingResult(
        entity="PM YASASVI",
        entity_type="government_scholarship_scheme",
        intent="verify_before_applying",
        expected_topics=topics,
    )
    processed = post_process_understanding(raw)

    assert "\n" not in processed.expected_topics[0].description
    assert "\r" not in processed.expected_topics[1].description
    assert processed.expected_topics[0].description == "Verify household income thresholds. Must not exceed limits."
    assert processed.expected_topics[0].label == "Eligibility Criteria"

    # Also verify entity_type and intent converted from snake_case to human phrases with spaces
    assert processed.entity_type == "government scholarship scheme"
    assert processed.intent == "verify before applying"


def test_has_year_or_currency_detection():
    from app.pipeline.query_understanding import has_year_or_currency

    # Should detect 4-digit years
    assert has_year_or_currency("Applications for 2024 cycle") is True
    assert has_year_or_currency("Valid until 2025") is True
    assert has_year_or_currency("Guidelines from 1998") is True

    # Should detect currencies
    assert has_year_or_currency("Income must not exceed Rs. 2.5 lakh") is True
    assert has_year_or_currency("Income limit is ₹250000") is True
    assert has_year_or_currency("Application fee is $50") is True
    assert has_year_or_currency("INR 50,000 allowance") is True
    assert has_year_or_currency("Allowance in rupees") is True

    # Generic statements without years or currencies should be clean
    assert has_year_or_currency("Check age, academic, and category eligibility rules") is False
    assert has_year_or_currency("Verify official portal submission deadline and cutoffs") is False
    assert has_year_or_currency("Check required identity and academic certificates") is False


def test_descriptions_with_year_or_currency_sanitized():
    topics = [
        ExpectedTopic(
            key="income_limit",
            label="Income Limit",
            importance=5,
            description="Verify family income below Rs. 2.5 lakh for 2025 cycle",
            is_critical=True,
        ),
        ExpectedTopic(key="deadline", label="Deadline", importance=5, description="Verify deadline", is_critical=True),
        ExpectedTopic(key="docs", label="Documents", importance=4, description="Required documents", is_critical=True),
        ExpectedTopic(key="portal", label="Portal", importance=4, description="Official portal link", is_critical=False),
        ExpectedTopic(key="renewal", label="Renewal", importance=3, description="Renewal policy", is_critical=False),
    ]
    raw = UnderstandingResult(
        entity="Scheme",
        entity_type="government scheme",
        intent="verify details",
        expected_topics=topics,
    )
    processed = post_process_understanding(raw)

    # 4-digit years and currency must be removed from description
    desc0 = processed.expected_topics[0].description
    assert "2025" not in desc0
    assert "Rs." not in desc0
    assert "lakh" not in desc0


def test_ambiguity_note_sanitized():
    topics = [
        ExpectedTopic(key=f"t_{i}", label=f"Topic {i}", importance=3, description="Verify details")
        for i in range(5)
    ]
    raw = UnderstandingResult(
        entity="PM YASASVI",
        entity_type="scholarship",
        intent="verification",
        expected_topics=topics,
        ambiguity_note="The scheme has sub-schemes like Component 1 for Class 9 and Component 2 for Class 11.",
    )
    processed = post_process_understanding(raw)

    # Must NOT name sub-schemes or categories from memory
    assert "Component 1" not in (processed.ambiguity_note or "")
    assert "Class 9" not in (processed.ambiguity_note or "")
    assert "refer to several programs or components" in (processed.ambiguity_note or "")


@pytest.mark.asyncio
async def test_understand_hygiene_reprompt_on_year_or_currency():
    """Verify understand() re-prompts once when topic descriptions contain year/currency."""
    # Turn 1: has offending year/currency
    turn1_payload = {
        "entity": "PM YASASVI",
        "entity_type": "government scholarship scheme",
        "intent": "verify before applying",
        "expected_topics": [
            {"key": "eligibility", "label": "Eligibility", "importance": 5, "description": "Income below Rs. 2.5 lakh in 2024", "is_critical": True},
            {"key": "deadline", "label": "Deadline", "importance": 5, "description": "Last date in 2025", "is_critical": True},
            {"key": "docs", "label": "Documents", "importance": 4, "description": "Certificates needed", "is_critical": True},
            {"key": "portal", "label": "Portal", "importance": 4, "description": "Official link", "is_critical": False},
            {"key": "renewal", "label": "Renewal", "importance": 3, "description": "Renewal rules", "is_critical": False},
        ],
        "needs_clarification": False,
    }
    # Turn 2: clean repaired response
    turn2_payload = {
        "entity": "PM YASASVI",
        "entity_type": "government scholarship scheme",
        "intent": "verify before applying",
        "expected_topics": [
            {"key": "eligibility", "label": "Eligibility", "importance": 5, "description": "Check family income and category requirements", "is_critical": True},
            {"key": "deadline", "label": "Deadline", "importance": 5, "description": "Verify portal closing and submission cutoff", "is_critical": True},
            {"key": "docs", "label": "Documents", "importance": 4, "description": "Certificates needed", "is_critical": True},
            {"key": "portal", "label": "Portal", "importance": 4, "description": "Official link", "is_critical": False},
            {"key": "renewal", "label": "Renewal", "importance": 3, "description": "Renewal rules", "is_critical": False},
        ],
        "needs_clarification": False,
    }

    class MultiTurnFakeClient:
        def __init__(self):
            self.call_count = 0

        async def generate_content(self, contents: str, schema: Any, system: str) -> FakeResponse:
            self.call_count += 1
            if self.call_count == 1:
                return FakeResponse(json.dumps(turn1_payload))
            return FakeResponse(json.dumps(turn2_payload))

    fake_client = MultiTurnFakeClient()
    set_client(fake_client)

    result = await understand("What should I verify before applying for PM YASASVI?")

    # Should have called twice (initial + 1 repair re-prompt)
    assert fake_client.call_count == 2
    assert "2024" not in result.expected_topics[0].description
    assert "Rs." not in result.expected_topics[0].description
    assert result.expected_topics[0].description == "Check family income and category requirements"

