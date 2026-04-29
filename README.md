# Coordinator

This service is the prototype 1 control plane.

It accepts:
- worker WebSocket connections on `/ws/worker`
- client WebSocket connections on `/ws/client`

It exposes:
- `GET /health`
- `GET /nodes`
- `GET /jobs`
- `GET /jobs/{job_id}`
- `GET /events/jobs`
- `GET /events/nodes`

## Run

```powershell
D:\Drive\TMXT\Project\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Build Exe

```powershell
powershell -ExecutionPolicy Bypass -File D:\Drive\TMXT\Project\apps\coordinator\build_coordinator.ps1
```

The packaged executable is written to:

- `D:\Drive\TMXT\Project\apps\dist\coordinator\tmxt-coordinator.exe`

For local prototype testing, clients and workers can use:

- `ws://127.0.0.1:8000/ws/client`
- `ws://127.0.0.1:8000/ws/worker`

For multi-machine testing on a LAN, replace `127.0.0.1` with the coordinator machine's LAN IP.
