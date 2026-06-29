# app/services/models.py
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ComponentStatus(str, Enum):
    """Operational status of a single health-checked component."""

    OK = 'ok'
    DEGRADED = 'degraded'
    ERROR = 'error'


class ComponentHealth(BaseModel, frozen=True):
    """Health result for one system component."""

    status: ComponentStatus
    message: str = ''


class HealthReport(BaseModel, frozen=True):
    """Aggregate health status returned by HealthService.check().

    The top-level status is the worst status across all components:
    ERROR > DEGRADED > OK.
    """

    status: ComponentStatus
    vector_store: ComponentHealth
    llm: ComponentHealth
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class IndexStats(BaseModel, frozen=True):
    """Statistics returned by IndexingService.rebuild()."""

    total_chunks: int = Field(ge=0)
    documents: list[str]
    elapsed_ms: float = Field(ge=0.0)
