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

When running the packaged executable, settings can be supplied in a `coordinator.env`
file placed beside `tmxt-coordinator.exe`.

## Docker

```powershell
docker build -t tmxt-coordinator .
docker run --rm -p 8000:8000 --env-file .env.example tmxt-coordinator
```

The container uses:

- `COORDINATOR_HOST=0.0.0.0`
- `COORDINATOR_PORT=8000`
- `COORDINATOR_DB_PATH=/tmp/coordinator.db`

## Northflank

This repo is ready to deploy as a Northflank combined service from Git.

Recommended setup:

- Build type: `Dockerfile`
- Dockerfile path: `/Dockerfile`
- Build context: `/`
- Public port: `8000`
- Protocol: `HTTP`
- Health check path: `/health`

Runtime variables:

- `WORKER_TOKEN`
- `COORDINATOR_HOST=0.0.0.0`
- `COORDINATOR_PORT=8000`
- `COORDINATOR_DB_PATH=/tmp/coordinator.db`
- `HEARTBEAT_TIMEOUT_SECONDS=15`
- `ASSIGNMENT_TIMEOUT_SECONDS=10`
- `MAX_JOB_RETRIES=1`

After deploy, use the generated public hostname for both:

- `wss://<northflank-domain>/ws/client`
- `wss://<northflank-domain>/ws/worker`

## Build Exe

```powershell
powershell -ExecutionPolicy Bypass -File D:\Drive\TMXT\Project\apps\coordinator\build_coordinator.ps1
```

The packaged executable is written to:

- `D:\Drive\TMXT\Project\apps\dist\coordinator\tmxt-coordinator.exe`
- `D:\Drive\TMXT\Project\apps\dist\coordinator\coordinator.env.example`

For local prototype testing, clients and workers can use:

- `ws://127.0.0.1:8000/ws/client`
- `ws://127.0.0.1:8000/ws/worker`

For multi-machine testing on a LAN, replace `127.0.0.1` with the coordinator machine's LAN IP.

## ngrok Autostart

The packaged coordinator can automatically launch ngrok when it starts.

Requirements:

- `ngrok.exe` must be either:
  - beside `tmxt-coordinator.exe`, or
  - available on `PATH`, or
  - referenced by `NGROK_PATH`
- ngrok must be authenticated either through:
  - `NGROK_AUTHTOKEN` in `coordinator.env`, or
  - an existing ngrok login/config on the machine

Suggested packaged setup:

1. Copy `coordinator.env.example` to `coordinator.env`
2. Set `NGROK_AUTOSTART=1`
3. Set `NGROK_AUTHTOKEN=...`
4. Optionally set `NGROK_URL=https://your-assigned-name.ngrok-free.app`
5. Put `ngrok.exe` beside `tmxt-coordinator.exe`

On startup, the coordinator will print:

- the detected ngrok public URL
- the worker websocket endpoint
- the client websocket endpoint
