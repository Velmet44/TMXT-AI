from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.utcnow()


def iso_now() -> str:
    return utc_now().replace(microsecond=0).isoformat() + "Z"


class Envelope(BaseModel):
    type: str
    request_id: str | None = None
    timestamp: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NodeRegistration(BaseModel):
    node_id: str
    token: str
    models: list[str] = Field(default_factory=list)
    cpu: str | None = None
    ram_gb: float = 0
    gpu_name: str | None = None
    vram_gb: float = 0
    ping_ms: float = 0
    tokens_per_sec: float = 0


class NodeHeartbeat(BaseModel):
    busy: bool = False
    active_job_id: str | None = None
    ping_ms: float = 0
    tokens_per_sec: float | None = None


class ClientJobRequest(BaseModel):
    session_id: str
    prompt: str
    requested_model: str


class JobSummary(BaseModel):
    job_id: str
    session_id: str
    requested_model: str
    status: str
    assigned_node_id: str | None
    retry_count: int
    created_at: str
    started_at: str | None
    completed_at: str | None
    error_reason: str | None


@dataclass
class NodeState:
    node_id: str
    websocket: Any
    models: list[str]
    cpu: str | None
    ram_gb: float
    gpu_name: str | None
    vram_gb: float
    ping_ms: float
    tokens_per_sec: float
    busy: bool = False
    active_job_id: str | None = None
    failure_count: int = 0
    success_count: int = 0
    status: str = "online"
    last_heartbeat: datetime = field(default_factory=utc_now)
    connected_at: datetime = field(default_factory=utc_now)
    remote_address: str | None = None
    last_error: str | None = None

    @property
    def total_jobs(self) -> int:
        return self.failure_count + self.success_count

    @property
    def fail_rate(self) -> float:
        return self.failure_count / self.total_jobs if self.total_jobs else 0.0


@dataclass
class JobState:
    job_id: str
    session_id: str
    prompt: str
    requested_model: str
    client_websocket: Any
    status: str = "queued"
    assigned_node_id: str | None = None
    retry_count: int = 0
    created_at: datetime = field(default_factory=utc_now)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_reason: str | None = None
    stream_chunks: list[str] = field(default_factory=list)

    def as_summary(self) -> JobSummary:
        return JobSummary(
            job_id=self.job_id,
            session_id=self.session_id,
            requested_model=self.requested_model,
            status=self.status,
            assigned_node_id=self.assigned_node_id,
            retry_count=self.retry_count,
            created_at=self.created_at.replace(microsecond=0).isoformat() + "Z",
            started_at=self.started_at.replace(microsecond=0).isoformat() + "Z" if self.started_at else None,
            completed_at=self.completed_at.replace(microsecond=0).isoformat() + "Z" if self.completed_at else None,
            error_reason=self.error_reason,
        )
