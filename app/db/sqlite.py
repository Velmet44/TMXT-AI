from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class Database:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS node_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    node_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def log_node_event(self, node_id: str, event_type: str, payload: dict[str, Any], created_at: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO node_events (node_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (node_id, event_type, json.dumps(payload), created_at),
            )
            connection.commit()

    def log_job_event(self, job_id: str, event_type: str, payload: dict[str, Any], created_at: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO job_events (job_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (job_id, event_type, json.dumps(payload), created_at),
            )
            connection.commit()

    def recent_job_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT job_id, event_type, payload, created_at FROM job_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "job_id": row["job_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def recent_node_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT node_id, event_type, payload, created_at FROM node_events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "node_id": row["node_id"],
                "event_type": row["event_type"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
