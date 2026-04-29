from __future__ import annotations

import asyncio
from datetime import timedelta

from fastapi import WebSocket

from ..core.config import settings
from ..db.sqlite import Database
from .models import NodeHeartbeat, NodeRegistration, NodeState, iso_now, utc_now
from .scheduler import is_node_eligible, score_node


class NodeRegistry:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.nodes: dict[str, NodeState] = {}
        self._lock = asyncio.Lock()

    async def register(self, registration: NodeRegistration, websocket: WebSocket) -> NodeState:
        async with self._lock:
            previous = self.nodes.get(registration.node_id)
            if previous is not None:
                previous.status = "offline"
                previous.last_error = "Replaced by a new connection"
                try:
                    await previous.websocket.close(code=1012)
                except Exception:
                    pass
            node = NodeState(
                node_id=registration.node_id,
                websocket=websocket,
                models=registration.models,
                cpu=registration.cpu,
                ram_gb=registration.ram_gb,
                gpu_name=registration.gpu_name,
                vram_gb=registration.vram_gb,
                ping_ms=registration.ping_ms,
                tokens_per_sec=registration.tokens_per_sec,
                remote_address=self._remote_address_from(websocket),
            )
            self.nodes[node.node_id] = node
            self.database.log_node_event(node.node_id, "node.registered", registration.model_dump(), iso_now())
            return node

    async def apply_heartbeat(self, node_id: str, heartbeat: NodeHeartbeat) -> None:
        async with self._lock:
            node = self.nodes[node_id]
            node.last_heartbeat = utc_now()
            node.busy = heartbeat.busy
            node.active_job_id = heartbeat.active_job_id
            node.ping_ms = heartbeat.ping_ms
            if heartbeat.tokens_per_sec is not None:
                node.tokens_per_sec = heartbeat.tokens_per_sec
            if node.status != "online":
                node.status = "online"
            node.last_error = None
            self.database.log_node_event(node_id, "node.heartbeat", heartbeat.model_dump(), iso_now())

    async def release_job(self, node_id: str, success: bool) -> None:
        async with self._lock:
            node = self.nodes.get(node_id)
            if not node:
                return
            node.busy = False
            node.active_job_id = None
            if success:
                node.success_count += 1
            else:
                node.failure_count += 1

    async def mark_offline(self, node_id: str, reason: str, *, keep_socket: bool = False) -> None:
        async with self._lock:
            node = self.nodes.get(node_id)
            if not node:
                return
            node.status = "offline"
            node.busy = False
            node.active_job_id = None
            node.last_error = reason
            if not keep_socket:
                node.websocket = None
            self.database.log_node_event(node_id, "node.offline", {"reason": reason}, iso_now())

    async def remove(self, node_id: str, reason: str) -> None:
        await self.mark_offline(node_id, reason)

    async def get_best_node(self, requested_model: str) -> NodeState | None:
        async with self._lock:
            self._expire_stale_nodes()
            candidates = [node for node in self.nodes.values() if is_node_eligible(node, requested_model)]
            if not candidates:
                return None
            candidates.sort(key=score_node, reverse=True)
            chosen = candidates[0]
            chosen.busy = True
            return chosen

    async def snapshot(self) -> list[dict[str, object]]:
        async with self._lock:
            self._expire_stale_nodes()
            return [
                {
                    "node_id": node.node_id,
                    "status": node.status,
                    "busy": node.busy,
                    "active_job_id": node.active_job_id,
                    "models": node.models,
                    "cpu": node.cpu,
                    "ram_gb": node.ram_gb,
                    "gpu_name": node.gpu_name,
                    "vram_gb": node.vram_gb,
                    "ping_ms": node.ping_ms,
                    "tokens_per_sec": node.tokens_per_sec,
                    "score": round(score_node(node), 3) if node.status == "online" and not node.busy else None,
                    "fail_rate": round(node.fail_rate, 4),
                    "failure_count": node.failure_count,
                    "success_count": node.success_count,
                    "remote_address": node.remote_address,
                    "connected_at": node.connected_at.replace(microsecond=0).isoformat() + "Z",
                    "last_heartbeat": node.last_heartbeat.replace(microsecond=0).isoformat() + "Z",
                    "last_error": node.last_error,
                }
                for node in self.nodes.values()
            ]

    def _expire_stale_nodes(self) -> None:
        cutoff = utc_now() - timedelta(seconds=settings.heartbeat_timeout_seconds)
        for node in self.nodes.values():
            if node.last_heartbeat < cutoff and node.status != "offline":
                node.status = "offline"
                node.busy = False
                node.active_job_id = None
                node.last_error = "Heartbeat timeout"

    @staticmethod
    def _remote_address_from(websocket: WebSocket) -> str | None:
        client = websocket.client
        if client is None:
            return None
        return f"{client.host}:{client.port}"
