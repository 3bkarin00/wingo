"""P10 API service (plan.md §4: "FastAPI, Pydantic v2 — schema validation,
job lifecycle, artifact serving, WebSocket progress"). Run with:

    uvicorn backend.api.main:app --reload --port 8000

CORS is wide-open (`allow_origins=["*"]`) — this is a local dev tool run
inside the Coder workspace (CLAUDE.md environment section), not a public
deployment; tighten before this is ever exposed beyond localhost/the
workspace's forwarded ports.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import configs, jobs

app = FastAPI(title="WingStructGen API", version="0.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(configs.router)
app.include_router(jobs.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
