"""
provider.py — Core LLM provider layer for Traceable.

Phase 2 implementation:
- Structured JSON output with Gemini via official google-genai SDK
- Native response schema validation via Pydantic v2
- Automatic single repair retry on schema/JSON mismatch
- Exponential backoff with jitter on 429/5xx and timeouts
- Concurrency control via asyncio.Semaphore
- SQLite response caching with SHA-256 keys
- Transparent, privacy-preserving logging (no secrets or sensitive prompt text logged)
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Type, TypeVar

import aiosqlite
from pydantic import BaseModel, ValidationError

from ..config import settings
from .errors import (
    LLMConfigError,
    LLMError,
    LLMOutputError,
    LLMUnavailableError,
)

logger = logging.getLogger("traceable.llm")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(levelname)s] %(asctime)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

T = TypeVar("T", bound=BaseModel)

# Lazy client and concurrency semaphore
_client: Any = None
_semaphore: Optional[asyncio.Semaphore] = None
_initialized_dbs: set[str] = set()
_cache_init_lock = asyncio.Lock()


def get_client() -> Any:
    """Lazily instantiate or return the global SDK client."""
    global _client
    if _client is not None:
        return _client

    if settings.LLM_PROVIDER != "gemini":
        raise LLMConfigError(f"Only 'gemini' is implemented (configured: {settings.LLM_PROVIDER!r})")

    api_key = settings.GEMINI_API_KEY
    if not api_key or not api_key.strip():
        raise LLMConfigError("GEMINI_API_KEY missing or rejected; check backend/.env")

    # Native google-genai SDK
    try:
        from google import genai
        _client = genai.Client(api_key=api_key.strip())
        return _client
    except ImportError as e:
        raise LLMConfigError(f"Failed to import google-genai SDK: {e}")
    except Exception as e:
        raise LLMConfigError(f"Failed to initialize Gemini client: {e}")


def set_client(client: Any) -> None:
    """Inject a client instance (used for testing with fake clients)."""
    global _client
    _client = client


def reset_client() -> None:
    """Reset injected client and semaphore back to default lazy initialization."""
    global _client, _semaphore
    _client = None
    _semaphore = None


def provider_info() -> dict[str, str]:
    """Return public provider metadata (no secrets)."""
    if settings.LLM_PROVIDER != "gemini":
        raise LLMConfigError(f"Only 'gemini' is implemented (configured: {settings.LLM_PROVIDER!r})")
    return {
        "provider": "gemini",
        "model": settings.GEMINI_MODEL,
    }


def _get_semaphore() -> asyncio.Semaphore:
    """Return the global semaphore bound to the current event loop."""
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.LLM_MAX_CONCURRENCY)
    return _semaphore


async def _init_cache_table(db_path: str) -> None:
    """Ensure llm_cache table exists in the configured SQLite database."""
    abs_path = str(Path(db_path).resolve())
    if abs_path in _initialized_dbs:
        return

    async with _cache_init_lock:
        if abs_path in _initialized_dbs:
            return
        Path(abs_path).parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(abs_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS llm_cache (
                    key TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    model TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.commit()
        _initialized_dbs.add(abs_path)


def _compute_cache_key(
    model: str,
    temperature: float,
    system: str,
    prompt: str,
    schema: Type[BaseModel],
) -> str:
    """Compute deterministic SHA-256 cache key."""
    schema_json = json.dumps(schema.model_json_schema(), sort_keys=True)
    raw = f"{model}:{temperature}:{system}:{prompt}:{schema_json}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clean_json_output(raw_text: str) -> str:
    """Strip optional markdown code block fencing from response text."""
    text = raw_text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if len(lines) >= 2:
            first = lines[0].strip()
            last = lines[-1].strip()
            if first.startswith("```") and last == "```":
                return "\n".join(lines[1:-1]).strip()
    return text


def _is_auth_error(exc: Exception) -> bool:
    """Check if exception represents an authentication or configuration failure."""
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status_code in (401, 403):
        return True
    msg = str(exc).lower()
    return "401" in msg or "403" in msg or "unauthorized" in msg or "permission denied" in msg or "invalid api key" in msg


def _is_transient_error(exc: Exception) -> bool:
    """Check if exception represents a retryable rate limit or server error."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status_code in (429, 500, 502, 503, 504):
        return True
    msg = str(exc).lower()
    return any(err in msg for err in ("429", "500", "502", "503", "504", "resource exhausted", "overloaded", "quota"))


def _extract_retry_after(exc: Exception) -> Optional[float]:
    """Extract Retry-After delay if hinted by error or headers."""
    retry_after = getattr(exc, "retry_after", None)
    if retry_after is not None:
        try:
            return float(retry_after)
        except (ValueError, TypeError):
            pass
    return None


async def _call_gemini_raw(
    client: Any,
    prompt: str,
    schema: Type[BaseModel],
    system: str,
) -> tuple[str, Optional[int]]:
    """Invoke Gemini with structured output. Return (response_text, token_count)."""
    # 1. Custom fake client for testing
    if hasattr(client, "generate_content"):
        res = client.generate_content(
            contents=prompt,
            schema=schema,
            system=system,
        )
        if asyncio.iscoroutine(res):
            res = await res
        text = getattr(res, "text", "") or ""
        tokens = getattr(res, "total_tokens", None)
        return text, tokens

    # 2. Native google-genai SDK client
    from google.genai import types

    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=schema,
        temperature=settings.LLM_TEMPERATURE,
        system_instruction=system if system else None,
    )

    def _sync_call() -> tuple[str, Optional[int]]:
        resp = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=config,
        )
        t = (resp.text or "").strip()
        tokens = None
        if hasattr(resp, "usage_metadata") and resp.usage_metadata is not None:
            tokens = getattr(resp.usage_metadata, "total_token_count", None)
        return t, tokens

    return await asyncio.to_thread(_sync_call)


async def generate_json(
    prompt: str,
    schema: Type[T],
    system: str = "",
    *,
    cache: bool = True,
    task: str = "generic",
) -> T:
    """Generate structured JSON conforming to `schema` using Gemini.

    Parameters:
      prompt: The user query or task instruction.
      schema: Pydantic v2 model class defining expected output schema.
      system: Optional system instruction.
      cache: Whether to read/write response from SQLite cache (default True).
      task: Label for telemetry/logging (e.g. "extraction", "understand").

    Returns:
      Validated instance of `schema`.
    """
    if settings.LLM_PROVIDER != "gemini":
        raise LLMConfigError(f"Only 'gemini' is implemented (configured: {settings.LLM_PROVIDER!r})")

    db_path = settings.SQLITE_DB_PATH
    model = settings.GEMINI_MODEL
    temp = settings.LLM_TEMPERATURE
    use_cache = cache and settings.LLM_CACHE_ENABLED

    # Cache lookup
    cache_key = _compute_cache_key(model, temp, system, prompt, schema)
    if use_cache:
        await _init_cache_table(db_path)
        try:
            async with aiosqlite.connect(db_path) as db:
                async with db.execute(
                    "SELECT response_json FROM llm_cache WHERE key = ?",
                    (cache_key,),
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        cached_json = row[0]
                        validated = schema.model_validate_json(cached_json)
                        logger.info(
                            "[LLM] task=%s model=%s cache=HIT latency_ms=0.0 attempts=0",
                            task,
                            model,
                        )
                        return validated
        except Exception as e:
            logger.warning("[LLM] Cache read error: %s (continuing with live call)", e)

    client = get_client()
    semaphore = _get_semaphore()

    start_time = time.perf_counter()
    attempts = 0
    total_tokens: Optional[int] = None
    validated_obj: Optional[T] = None
    raw_response_text = ""

    async with semaphore:
        current_prompt = prompt
        repair_attempted = False

        while True:
            # Outer transient retry loop (up to 3 attempts total)
            attempt_exc: Optional[Exception] = None
            for transient_attempt in range(1, 4):
                attempts += 1
                try:
                    raw_response_text, total_tokens = await asyncio.wait_for(
                        _call_gemini_raw(client, current_prompt, schema, system),
                        timeout=settings.LLM_TIMEOUT_SECONDS,
                    )
                    attempt_exc = None
                    break
                except Exception as exc:
                    attempt_exc = exc
                    if _is_auth_error(exc):
                        raise LLMConfigError("GEMINI_API_KEY missing or rejected; check backend/.env") from exc

                    if _is_transient_error(exc):
                        if transient_attempt < 3:
                            delay = _extract_retry_after(exc)
                            if delay is None:
                                delay = (2 ** (transient_attempt - 1)) + random.uniform(0.1, 0.5)
                            logger.warning(
                                "[LLM] Transient error attempt %d/3 (%s). Backing off %.2fs...",
                                transient_attempt,
                                type(exc).__name__,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue
                        else:
                            raise LLMUnavailableError(
                                f"Service unavailable after {transient_attempt} attempts: {exc}"
                            ) from exc
                    # Other unknown fatal error
                    raise exc

            if attempt_exc is not None:
                raise LLMUnavailableError(f"LLM call failed: {attempt_exc}") from attempt_exc

            # Parsing and schema validation
            cleaned = _clean_json_output(raw_response_text)
            try:
                parsed_dict = json.loads(cleaned)
                validated_obj = schema.model_validate(parsed_dict)
                break  # Successful parsing and validation!
            except (json.JSONDecodeError, ValidationError) as parse_err:
                if not repair_attempted:
                    repair_attempted = True
                    err_preview = str(parse_err)[:200].replace("\n", " ")
                    logger.warning("[LLM] Validation failed (%s). Triggering repair retry...", err_preview)
                    current_prompt = (
                        f"{prompt}\n\n"
                        f"Your previous output was invalid: {err_preview}. "
                        "Return only valid JSON matching the schema."
                    )
                    continue  # Run the loop once more with repair prompt
                else:
                    raise LLMOutputError(
                        f"Validation failed after repair retry: {parse_err}"
                    ) from parse_err

    # Compute latency
    latency_ms = (time.perf_counter() - start_time) * 1000.0

    # Write to SQLite cache if successful
    if use_cache and validated_obj is not None:
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            payload = validated_obj.model_dump_json()
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    """
                    INSERT OR REPLACE INTO llm_cache (key, response_json, model, created_at)
                    VALUES (?, ?, ?, ?)
                    """,
                    (cache_key, payload, model, now_iso),
                )
                await db.commit()
        except Exception as cache_err:
            logger.warning("[LLM] Failed to write cache: %s", cache_err)

    # Logging telemetry
    tokens_str = f" tokens={total_tokens}" if total_tokens is not None else ""
    logger.info(
        "[LLM] task=%s model=%s cache=MISS latency_ms=%.1f attempts=%d%s",
        task,
        model,
        latency_ms,
        attempts,
        tokens_str,
    )

    return validated_obj
