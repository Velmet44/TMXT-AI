from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from ..core.config import settings
from ..db.sqlite import Database
from .models import ClientJobRequest, JobState, NodeState, iso_now, utc_now
from .node_registry import NodeRegistry


class JobManager:
    def __init__(self, node_registry: NodeRegistry, database: Database) -> None:
        self.node_registry = node_registry
        self.database = database
        self.jobs: dict[str, JobState] = {}
        self.assignment_timeouts: dict[str, asyncio.Task[None]] = {}
        self._lock = asyncio.Lock()

    async def create_job(self, request: ClientJobRequest, client_websocket: WebSocket) -> JobState:
        job = JobState(
            job_id=f"job_{uuid.uuid4().hex[:10]}",
            session_id=request.session_id,
            prompt=request.prompt,
            requested_model=request.requested_model,
            client_websocket=client_websocket,
        )
        async with self._lock:
            self.jobs[job.job_id] = job
        self.database.log_job_event(job.job_id, "job.queued", request.model_dump(), iso_now())
        await self._send_client_event(job, "job.queued", {"job_id": job.job_id, "requested_model": job.requested_model})
        return job

    async def assign_job(self, job: JobState) -> bool:
        node = await self.node_registry.get_best_node(job.requested_model)
        if node is None:
            job.status = "failed"
            job.error_reason = "No eligible workers available"
            self.database.log_job_event(job.job_id, "job.fail", {"reason": job.error_reason}, iso_now())
            await self._send_client_event(job, "job.fail", {"job_id": job.job_id, "reason": job.error_reason})
            return False

        job.status = "assigned"
        job.assigned_node_id = node.node_id
        node.active_job_id = job.job_id
        payload = {
            "job_id": job.job_id,
            "prompt": job.prompt,
            "requested_model": job.requested_model,
            "retry_count": job.retry_count,
        }
        try:
            await node.websocket.send_json({"type": "job.assigned", "timestamp": iso_now(), "payload": payload})
        except Exception as exc:
            await self.node_registry.mark_offline(node.node_id, f"Assignment send failed: {exc}")
            await self.node_registry.release_job(node.node_id, success=False)
            return await self.fail_job(job.job_id, node.node_id, f"Assignment send failed: {exc}", retryable=True)
        self.database.log_job_event(job.job_id, "job.assigned", {"node_id": node.node_id}, iso_now())
        await self._send_client_event(job, "job.started", {"job_id": job.job_id, "node_id": node.node_id})
        self.assignment_timeouts[job.job_id] = asyncio.create_task(self._watch_assignment_timeout(job.job_id, node.node_id))
        return True

    async def accept_job(self, job_id: str, node_id: str) -> None:
        job = self.jobs[job_id]
        if job.assigned_node_id != node_id:
            return
        job.status = "running"
        job.started_at = utc_now()
        timeout_task = self.assignment_timeouts.pop(job_id, None)
        if timeout_task:
            timeout_task.cancel()
        self.database.log_job_event(job_id, "job.accepted", {"node_id": node_id}, iso_now())

    async def stream_chunk(self, job_id: str, node_id: str, chunk: str) -> None:
        job = self.jobs[job_id]
        if job.assigned_node_id != node_id:
            return
        job.status = "streaming"
        job.stream_chunks.append(chunk)
        await self._send_client_event(job, "job.stream", {"job_id": job_id, "node_id": node_id, "chunk": chunk})

    async def complete_job(self, job_id: str, node_id: str, text: str, metrics: dict[str, Any]) -> None:
        job = self.jobs[job_id]
        if job.assigned_node_id != node_id:
            return
        job.status = "completed"
        job.completed_at = utc_now()
        job.error_reason = None
        timeout_task = self.assignment_timeouts.pop(job_id, None)
        if timeout_task:
            timeout_task.cancel()
        await self.node_registry.release_job(node_id, success=True)
        self.database.log_job_event(job_id, "job.complete", {"node_id": node_id, "metrics": metrics}, iso_now())
        await self._send_client_event(
            job,
            "job.complete",
            {
                "job_id": job_id,
                "node_id": node_id,
                "text": text,
                "metrics": metrics,
                "duration_seconds": self._duration_seconds(job.started_at, job.completed_at),
            },
        )

    async def fail_job(self, job_id: str, node_id: str | None, reason: str, retryable: bool) -> None:
        job = self.jobs[job_id]
        if node_id and job.assigned_node_id and job.assigned_node_id != node_id:
            return
        timeout_task = self.assignment_timeouts.pop(job_id, None)
        if timeout_task:
            timeout_task.cancel()
        if node_id:
            await self.node_registry.release_job(node_id, success=False)

        if retryable and job.retry_count < settings.max_job_retries:
            job.retry_count += 1
            job.status = "queued"
            previous_node_id = job.assigned_node_id
            job.assigned_node_id = None
            job.error_reason = reason
            self.database.log_job_event(job_id, "job.retrying", {"reason": reason, "previous_node_id": previous_node_id}, iso_now())
            await self._send_client_event(
                job,
                "job.retrying",
                {"job_id": job_id, "reason": reason, "retry_count": job.retry_count},
            )
            await self.assign_job(job)
            return

        job.status = "failed"
        job.error_reason = reason
        job.completed_at = utc_now()
        self.database.log_job_event(job_id, "job.fail", {"reason": reason}, iso_now())
        await self._send_client_event(job, "job.fail", {"job_id": job_id, "reason": reason})

    async def cancel_job(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return
        job.status = "cancelled"
        self.database.log_job_event(job_id, "job.cancel", {}, iso_now())
        if job.assigned_node_id:
            node = self.node_registry.nodes.get(job.assigned_node_id)
            if node and node.status == "online" and node.websocket is not None:
                await node.websocket.send_json({"type": "job.cancel", "timestamp": iso_now(), "payload": {"job_id": job_id}})
        await self._send_client_event(job, "job.cancel", {"job_id": job_id})

    async def _send_client_event(self, job: JobState, event_type: str, payload: dict[str, Any]) -> None:
        if job.client_websocket.application_state == WebSocketState.DISCONNECTED:
            return
        await job.client_websocket.send_json({"type": event_type, "timestamp": iso_now(), "payload": payload})

    async def snapshot_jobs(self) -> list[dict[str, Any]]:
        async with self._lock:
            jobs = sorted(self.jobs.values(), key=lambda item: item.created_at, reverse=True)
            return [job.as_summary().model_dump() for job in jobs]

    async def get_job(self, job_id: str) -> dict[str, Any] | None:
        async with self._lock:
            job = self.jobs.get(job_id)
            if job is None:
                return None
            payload = job.as_summary().model_dump()
            payload["stream_preview"] = "".join(job.stream_chunks)[-2000:]
            return payload

    async def _watch_assignment_timeout(self, job_id: str, node_id: str) -> None:
        try:
            await asyncio.sleep(settings.assignment_timeout_seconds)
            job = self.jobs.get(job_id)
            if job and job.status == "assigned" and job.assigned_node_id == node_id:
                await self.fail_job(job_id, node_id, "Worker did not accept the job in time", retryable=True)
        except asyncio.CancelledError:
            return

    @staticmethod
    def _duration_seconds(started_at: datetime | None, completed_at: datetime | None) -> float | None:
        if not started_at or not completed_at:
            return None
        return round((completed_at - started_at).total_seconds(), 3)
