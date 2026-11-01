"""
Traceable API — main entry point.

Includes health check, source acquisition endpoints, and query understanding.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.sources import router as sources_router
from .api.understand import router as understand_router

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

app.include_router(sources_router)
app.include_router(understand_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "app": "traceable"}
