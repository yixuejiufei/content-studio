from __future__ import annotations

import json
import os
import sqlite3
import threading
from pathlib import Path

from .schemas import ContentTask, RenderJob


class SQLiteStore:
    def __init__(self, database_path: str | None = None) -> None:
        path = database_path or os.getenv("CONTENT_STUDIO_DB_PATH", str(Path(__file__).resolve().parent.parent / "content-studio.db"))
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._connection:
            self._connection.execute("""CREATE TABLE IF NOT EXISTS content_tasks (
                task_id TEXT PRIMARY KEY, task_json TEXT NOT NULL,
                created_at REAL NOT NULL, updated_at REAL NOT NULL)""")
            self._connection.execute("""CREATE TABLE IF NOT EXISTS render_jobs (
                job_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, job_json TEXT NOT NULL,
                created_at REAL NOT NULL)""")

    def save(self, task: ContentTask) -> None:
        with self._lock, self._connection:
            self._connection.execute("""INSERT INTO content_tasks(task_id, task_json, created_at, updated_at)
                VALUES (?, ?, ?, ?) ON CONFLICT(task_id) DO UPDATE SET task_json=excluded.task_json, updated_at=excluded.updated_at""",
                (task.task_id, task.model_dump_json(), task.created_at, task.updated_at))

    def get(self, task_id: str) -> ContentTask | None:
        with self._lock:
            row = self._connection.execute("SELECT task_json FROM content_tasks WHERE task_id = ?", (task_id,)).fetchone()
        return ContentTask.model_validate_json(row["task_json"]) if row else None

    def list(self) -> list[ContentTask]:
        with self._lock:
            rows = self._connection.execute("SELECT task_json FROM content_tasks ORDER BY updated_at DESC").fetchall()
        return [ContentTask.model_validate_json(row["task_json"]) for row in rows]

    def save_render_job(self, job: RenderJob) -> None:
        with self._lock, self._connection:
            self._connection.execute("""INSERT INTO render_jobs(job_id, task_id, job_json, created_at)
                VALUES (?, ?, ?, ?) ON CONFLICT(job_id) DO UPDATE SET job_json=excluded.job_json""",
                (job.job_id, job.task_id, job.model_dump_json(), job.created_at))

    def get_render_job(self, job_id: str) -> RenderJob | None:
        with self._lock:
            row = self._connection.execute("SELECT job_json FROM render_jobs WHERE job_id = ?", (job_id,)).fetchone()
        return RenderJob.model_validate_json(row["job_json"]) if row else None

    def list_render_jobs(self, task_id: str) -> list[RenderJob]:
        with self._lock:
            rows = self._connection.execute("SELECT job_json FROM render_jobs WHERE task_id = ? ORDER BY created_at DESC", (task_id,)).fetchall()
        return [RenderJob.model_validate_json(row["job_json"]) for row in rows]
