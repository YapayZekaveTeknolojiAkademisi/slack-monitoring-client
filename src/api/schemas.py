from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field("ok", description="Service health")


class StatusResponse(BaseModel):
    queue_ready: bool = Field(..., description="Queue manager is started")
    queue_size: int = Field(..., description="Current queue size")


class InfoResponse(BaseModel):
    log_dir: str = Field(..., description="Log directory")
    env: str = Field("", description="ENV (e.g. production)")


class ErrorLogsResponse(BaseModel):
    """error.log içeriği (son N kayıt)."""
    logs: List[Dict[str, Any]] = Field(default_factory=list, description="JSON error log entries")
    count: int = Field(0, description="Number of entries returned")


class BaseActionResponse(BaseModel):
    status: bool = Field(..., description="Action status")
    action: str = Field(..., description="Action name")
    message: str = Field(..., description="Action message")
    data: Optional[Dict[str, Any]] = Field(None, description="Action data")