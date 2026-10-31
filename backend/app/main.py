"""
Traceable API — main entry point.

Phase 0 scaffold: health check only.
Feature routers (understand, sources, analyses) will be added in later phases.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Traceable API",
    description="AI-Assisted Information Gap Detection Platform — Every finding, traced to its source.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "traceable"}
