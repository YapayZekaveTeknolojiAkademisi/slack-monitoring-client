from __future__ import annotations

import os

from fastapi import APIRouter, Query

from src.api.schemas import (
    ErrorLogsResponse,
    HealthResponse,
    InfoResponse,
    StatusResponse,
)
from src.services.log_service import LogService

router = APIRouter()


def _queue_ready_and_size() -> tuple[bool, int]:
    """Returns (queue_ready, queue_size). Safe when queue not started."""
    try:
        from src.listener import queue_server
        _ = queue_server.queue
        return True, queue_server.size()
    except (RuntimeError, Exception):
        return False, 0


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness: process is up."""
    return HealthResponse(status="ok")


@router.get("/monitoring/api/v1/status", response_model=StatusResponse)
def status() -> StatusResponse:
    """Queue and listener status."""
    ready, size = _queue_ready_and_size()
    return StatusResponse(queue_ready=ready, queue_size=size)


@router.get("/monitoring/api/v1/info", response_model=InfoResponse)
def info() -> InfoResponse:
    """Application info (read-only)."""
    return InfoResponse(
        log_dir=os.environ.get("LOG_DIR", "logs"),
        env=os.environ.get("ENV", ""),
    )


@router.get("/monitoring/api/v1/logs", response_model=ErrorLogsResponse)
def error_logs(
    limit: int = Query(100, ge=1, le=1000, description="Max number of error log entries to return"),
) -> ErrorLogsResponse:
    """error.log dosyasındaki hata kayıtlarını döndürür (JSON satırlar)."""
    log_service = LogService()
    logs = log_service.get_error_logs(limit=limit)
    return ErrorLogsResponse(logs=logs, count=len(logs))
