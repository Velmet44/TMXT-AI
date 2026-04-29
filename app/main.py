from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from app.core.config import settings
    from app.db.sqlite import Database
    from app.services.job_manager import JobManager
    from app.services.models import ClientJobRequest, Envelope, NodeHeartbeat, NodeRegistration, iso_now
    from app.services.node_registry import NodeRegistry
else:
    from .core.config import settings
    from .db.sqlite import Database
    from .services.job_manager import JobManager
    from .services.models import ClientJobRequest, Envelope, NodeHeartbeat, NodeRegistration, iso_now
    from .services.node_registry import NodeRegistry

database = Database(settings.db_path)
node_registry = NodeRegistry(database)
job_manager = JobManager(node_registry, database)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="TMXT Coordinator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/nodes")
async def list_nodes() -> list[dict[str, object]]:
    return await node_registry.snapshot()


@app.get("/jobs")
async def list_jobs() -> list[dict[str, object]]:
    return await job_manager.snapshot_jobs()


@app.get("/jobs/{job_id}")
async def get_job(job_id: str) -> dict[str, object]:
    job = await job_manager.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.get("/events/jobs")
async def recent_job_events(limit: int = 50) -> list[dict[str, object]]:
    return database.recent_job_events(limit=min(max(limit, 1), 200))


@app.get("/events/nodes")
async def recent_node_events(limit: int = 50) -> list[dict[str, object]]:
    return database.recent_node_events(limit=min(max(limit, 1), 200))


@app.websocket("/ws/worker")
async def worker_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    node_id: str | None = None
    try:
        while True:
            envelope = Envelope.model_validate(await websocket.receive_json())
            if envelope.type == "node.register":
                registration = NodeRegistration.model_validate(envelope.payload)
                if registration.token != settings.worker_token:
                    await websocket.send_json(
                        {"type": "error", "timestamp": iso_now(), "payload": {"reason": "Invalid worker token"}}
                    )
                    await websocket.close(code=1008)
                    return
                node = await node_registry.register(registration, websocket)
                node_id = node.node_id
                await websocket.send_json(
                    {"type": "node.registered", "timestamp": iso_now(), "payload": {"node_id": node.node_id}}
                )
            elif envelope.type == "node.heartbeat":
                if not node_id:
                    await websocket.send_json(
                        {"type": "error", "timestamp": iso_now(), "payload": {"reason": "Worker not registered"}}
                    )
                    continue
                heartbeat = NodeHeartbeat.model_validate(envelope.payload)
                await node_registry.apply_heartbeat(node_id, heartbeat)
            elif envelope.type == "job.accepted":
                await job_manager.accept_job(envelope.payload["job_id"], envelope.payload["node_id"])
            elif envelope.type == "job.stream":
                await job_manager.stream_chunk(
                    envelope.payload["job_id"],
                    envelope.payload["node_id"],
                    envelope.payload["chunk"],
                )
            elif envelope.type == "job.complete":
                await job_manager.complete_job(
                    envelope.payload["job_id"],
                    envelope.payload["node_id"],
                    envelope.payload["text"],
                    envelope.payload.get("metrics", {}),
                )
            elif envelope.type == "job.fail":
                await job_manager.fail_job(
                    envelope.payload["job_id"],
                    envelope.payload.get("node_id"),
                    envelope.payload["reason"],
                    envelope.payload.get("retryable", False),
                )
    except WebSocketDisconnect:
        if node_id:
            node = node_registry.nodes.get(node_id)
            if node and node.active_job_id:
                await job_manager.fail_job(
                    node.active_job_id,
                    node_id,
                    "Worker disconnected during job execution",
                    retryable=True,
                )
            await node_registry.remove(node_id, "Worker disconnected")


@app.websocket("/ws/client")
async def client_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            envelope = Envelope.model_validate(await websocket.receive_json())
            if envelope.type == "job.submit":
                request = ClientJobRequest.model_validate(envelope.payload)
                job = await job_manager.create_job(request, websocket)
                await job_manager.assign_job(job)
            elif envelope.type == "job.cancel":
                await job_manager.cancel_job(envelope.payload["job_id"])
    except WebSocketDisconnect:
        return


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port)
