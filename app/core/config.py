from __future__ import annotations

import os
import sys
from pathlib import Path


def _config_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _load_env_file() -> None:
    env_path = _config_base_dir() / "coordinator.env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


class Settings:
    host: str = os.getenv("COORDINATOR_HOST", "0.0.0.0")
    port: int = int(os.getenv("COORDINATOR_PORT", "8000"))
    db_path: str = os.getenv("COORDINATOR_DB_PATH", "coordinator.db")
    worker_token: str = os.getenv("WORKER_TOKEN", "prototype-secret")
    heartbeat_timeout_seconds: int = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "15"))
    assignment_timeout_seconds: int = int(os.getenv("ASSIGNMENT_TIMEOUT_SECONDS", "10"))
    max_job_retries: int = int(os.getenv("MAX_JOB_RETRIES", "1"))
    ngrok_autostart: bool = os.getenv("NGROK_AUTOSTART", "1").lower() not in {"0", "false", "no"}
    ngrok_path: str | None = os.getenv("NGROK_PATH") or None
    ngrok_authtoken: str | None = os.getenv("NGROK_AUTHTOKEN") or None
    ngrok_api_base_url: str = os.getenv("NGROK_API_BASE_URL", "http://127.0.0.1:4040/api")
    ngrok_url: str | None = os.getenv("NGROK_URL") or None


settings = Settings()
