from __future__ import annotations

from fastapi import FastAPI

from src.api.routes import router

app = FastAPI(
    title="Slack Monitoring System API",
    description="Health, status, and queue endpoints.",
    version="1.0.0",
)
app.include_router(router)
