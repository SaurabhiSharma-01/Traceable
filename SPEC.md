# Traceable: Spec

**Tagline:** Every finding, traced to its source.

> Hackathon problem statement: "Digital Dark Spot: AI-Assisted Information Gap Detection Platform" (Shinchan Online Hackathon 2026).
> This file is the single source of truth for the project. Read it fully before doing any work.

---

## 1. Problem

People research decisions (scholarships, admissions, government schemes, business rules) across scattered web pages. Search tools find pages. Summarizers condense them. Neither shows what is **missing**, what **conflicts**, or what is **outdated**.

Traceable takes a research question, collects real web sources, and reports:

- Information **gaps** and unanswered questions
- **Possible conflicts** between sources, shown side by side
- **Stale or undated** sources
- A **prioritized "verify next" checklist**

Every finding is traceable to a source quote. The UI clearly separates **sourced information** from **AI-generated suggestions** and **uncertainty**.

---

## 2. Non-negotiable rules

1. Every finding cites `source_id` + `passage_id` + a verbatim quote (except AI-suggested questions, which carry no evidence).
2. Code verifies that every LLM quote is a substring of the cited passage. Failed quotes are dropped or marked UNCERTAIN.
3. "Not found in the sources reviewed" is a valid, expected output. Never invent facts, quotes or dates.
4. The LLM never judges truth from its own memory. It only reads provided text.
5. AI-inferred items are labelled "Potential gap", "Possible conflict" or "AI-generated suggestion". Never use "verified" or "proven" for AI output.
6. Dates come from code. If none is found, the source is "undated". Never guess.
7. **No mock data, no demo corpus, no hardcoded results anywhere in the app.** All runs use real search and real LLM calls. Test fixtures live only in `backend/tests/`.
8. No invented UI claims: no fake stats, version badges, hash badges, cluster names, or percentages that the code does not actually compute.
9. One failing source or LLM call must never crash a run. Record it as a warning and continue.
10. The product never claims to prove truth. It grades evidence quality and tells the user what to verify.

---

## 3. Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, Pydantic v2, httpx, trafilatura, BeautifulSoup4, pdfplumber, python-dateutil, rapidfuzz, SQLite |
| LLM | Gemini via `app/llm/provider.py` (swappable). JSON output, temperature 0.1, schema validation, 1 retry, backoff on 429/5xx, cache by prompt hash |
| Search | Tavily via `SEARCH_API_KEY` (pluggable provider interface) |
| Frontend | React + Vite + TypeScript + Tailwind CSS |
| Design reference | `docs/design/screenshots/` and `docs/design/stitch-code/` |

Environment variables (`backend/.env`, never committed): `LLM_PROVIDER`, `GEMINI_API_KEY`, `SEARCH_API_KEY`, `STALE_MONTHS`.

---

## 4. Pipeline

| # | Step | Type | Output |
|---|---|---|---|
| 1 | **Understand question** | LLM (Module A) | Entity + 6-10 expected topics (editable by the user) |
| 2 | **Collect sources** | Code + search API | Candidate sources from Tavily search, user URLs, pasted text, PDFs. User can deselect |
| 3 | **Fetch, clean, date, chunk** | Code | Clean text, title, domain, source class, published date + origin, cycle year, passages with stable IDs (`S2-P5`) |
| 4 | **Extract facts** | LLM (Module B) | Per source and topic: found, value, verbatim quote, passage_id, cycle_year, confidence |
| 5 | **Verify quotes** | Code | `quote_verified` flag on every fact |
| 6 | **Analyse** | Code | Coverage matrix (topics x sources), gap findings, stale/undated findings |
| 7 | **Evidence quality** | Code | Independent-origin clustering, primary-source anchoring, evidence levels, risk signals |
| 8 | **Detect conflicts** | Code + LLM (Module C) | Rules for dates and numbers; LLM judge (same / different / unclear) for free text |
| 9 | **Suggest extra questions** | LLM (Module D) | Up to 5 questions, labelled AI-generated, no evidence attached |
| 10 | **Build checklist** | Code | Ranked verify-next actions linked to findings |
| 11 | **Orchestrate** | Code | Runs steps, streams progress (SSE), stores the Analysis in SQLite |

