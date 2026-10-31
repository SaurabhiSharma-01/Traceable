#!/usr/bin/env python3
"""
scripts/check_keys.py
─────────────────────
Validates that GEMINI_API_KEY and SEARCH_API_KEY are present and working.

Usage (from the backend/ directory):
    python scripts/check_keys.py

Each check prints PASS or FAIL with a clear message.
The actual key values are never printed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

# ── Load .env from backend/ ──────────────────────────────────────────────────
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    from dotenv import load_dotenv
    load_dotenv(env_path)
else:
    print(f"[WARN] No .env found at {env_path}. Falling back to environment variables.")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
SEARCH_API_KEY = os.getenv("SEARCH_API_KEY", "")

results: list[tuple[str, bool, str]] = []   # (check_name, passed, message)


# ── Check 1: Gemini ──────────────────────────────────────────────────────────
print("\n── Gemini API ──────────────────────────────────────────────────────────")

if not GEMINI_API_KEY:
    results.append(("Gemini", False, "GEMINI_API_KEY is empty. Get one at https://aistudio.google.com/app/apikey"))
else:
    gemini_passed = False
    details_log = []

    # Method A: Direct REST call (bypasses any SDK version mismatch)
    # 1. Fetch available models for this specific key
    available_models: list[str] = []
    for api_version in ["v1beta", "v1"]:
        try:
            req_url = f"https://generativelanguage.googleapis.com/{api_version}/models?key={GEMINI_API_KEY}"
            req = urllib.request.Request(req_url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for m in data.get("models", []):
                    methods = m.get("supportedGenerationMethods", [])
                    name = m.get("name", "")
                    if "generateContent" in methods:
                        # name is usually "models/gemini-..."
                        clean_name = name.replace("models/", "")
                        if clean_name not in available_models:
                            available_models.append(clean_name)
            if available_models:
                break
        except Exception as e:
            details_log.append(f"ListModels({api_version}): {e}")

    # Fallback candidate models if listing was empty
    priority_candidates = [
        "gemini-3.8-flash",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-pro",
    ]
    test_models = []
    # Add discovered models first
    for m in available_models:
        if m not in test_models:
            test_models.append(m)
    for m in priority_candidates:
        if m not in test_models:
            test_models.append(m)

    # 2. Test generation with each candidate model
    for model_name in test_models:
        # First try REST endpoint
        for api_version in ["v1beta", "v1"]:
            try:
                url = f"https://generativelanguage.googleapis.com/{api_version}/models/{model_name}:generateContent?key={GEMINI_API_KEY}"
                payload = json.dumps({
                    "contents": [{"parts": [{"text": "Say hello"}]}]
                }).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    resp_data = json.loads(resp.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if candidates:
                        text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                        print(f"  Gemini reply ({model_name} via {api_version}): {text!r}")
                        results.append(("Gemini", True, f"Response received using {model_name} ({len(text)} chars)"))
                        gemini_passed = True
                        break
            except urllib.error.HTTPError as he:
                try:
                    err_body = json.loads(he.read().decode("utf-8"))
                    msg = err_body.get("error", {}).get("message", str(he))
                except Exception:
                    msg = str(he)
                details_log.append(f"{model_name}({api_version}): {msg}")
            except Exception as ex:
                details_log.append(f"{model_name}({api_version}): {ex}")

        if gemini_passed:
            break

    # If REST didn't work, try SDKs as backup
    if not gemini_passed:
        try:
            from google import genai
            client = genai.Client(api_key=GEMINI_API_KEY)
            for m in ["gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                try:
                    r = client.models.generate_content(model=m, contents="Say hello")
                    txt = (r.text or "").strip()
                    print(f"  Gemini reply ({m} via SDK): {txt!r}")
                    results.append(("Gemini", True, f"Response received using {m} ({len(txt)} chars)"))
                    gemini_passed = True
                    break
                except Exception as sdk_err:
                    details_log.append(f"SDK({m}): {sdk_err}")
        except Exception:
            pass

    if not gemini_passed:
        # Show first 2 concise errors
        summary_err = " | ".join(details_log[:2]) if details_log else "Failed to connect"
        results.append(("Gemini", False, summary_err))


# ── Check 2: Tavily ──────────────────────────────────────────────────────────
print("\n── Tavily Search API ───────────────────────────────────────────────────")

if not SEARCH_API_KEY:
    results.append(("Tavily", False, "SEARCH_API_KEY is empty. Get one at https://app.tavily.com"))
else:
    try:
        from tavily import TavilyClient  # type: ignore
        client = TavilyClient(api_key=SEARCH_API_KEY)
        resp = client.search("scholarship eligibility", max_results=3)
        hits = resp.get("results", [])
        print(f"  Top {len(hits)} results:")
        for i, hit in enumerate(hits[:3], 1):
            print(f"    {i}. {hit.get('title', '(no title)')}")
            print(f"       {hit.get('url', '(no url)')}")
        results.append(("Tavily", True, f"{len(hits)} results returned"))
    except Exception as exc:
        results.append(("Tavily", False, str(exc)))


# ── Summary ──────────────────────────────────────────────────────────────────
print("\n── Results ─────────────────────────────────────────────────────────────")
all_passed = True
for name, passed, msg in results:
    status = "PASS ✓" if passed else "FAIL ✗"
    print(f"  {status}  {name}: {msg}")
    if not passed:
        all_passed = False

print()
sys.exit(0 if all_passed else 1)
