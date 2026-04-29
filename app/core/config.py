from __future__ import annotations

import os


class Settings:
    host: str = os.getenv("COORDINATOR_HOST", "0.0.0.0")
    port: int = int(os.getenv("COORDINATOR_PORT", "8000"))
    db_path: str = os.getenv("COORDINATOR_DB_PATH", "coordinator.db")
    worker_token: str = os.getenv("WORKER_TOKEN", "prototype-secret")
    heartbeat_timeout_seconds: int = int(os.getenv("HEARTBEAT_TIMEOUT_SECONDS", "15"))
    assignment_timeout_seconds: int = int(os.getenv("ASSIGNMENT_TIMEOUT_SECONDS", "10"))
    max_job_retries: int = int(os.getenv("MAX_JOB_RETRIES", "1"))


settings = Settings()
