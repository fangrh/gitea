from __future__ import annotations

import json
import sqlite3
import uuid
from pathlib import Path

from models import TaskRecord


class SchedulerStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    repo_key TEXT NOT NULL,
                    issue_number INTEGER,
                    comment_id INTEGER,
                    event_type TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    claimed_by TEXT,
                    session_id TEXT,
                    lease_expires_at TEXT,
                    phase TEXT,
                    summary TEXT,
                    payload_json TEXT,
                    result_json TEXT,
                    reply_comment_id INTEGER
                )
                """
            )

    def upsert_task(
        self,
        *,
        repo_key: str,
        issue_number: int | None,
        comment_id: int | None,
        event_type: str,
        dedupe_key: str,
        payload: dict,
        status: str = "queued",
    ) -> TaskRecord:
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        with self._connect() as conn:
            row = conn.execute("SELECT task_id FROM tasks WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
            if row:
                existing = self.get_task(str(row["task_id"]))
                if existing is None:
                    raise RuntimeError("Task lookup failed after dedupe hit")
                return existing
            conn.execute(
                """
                INSERT INTO tasks (
                    task_id, repo_key, issue_number, comment_id, event_type, dedupe_key,
                    status, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    repo_key,
                    issue_number,
                    comment_id,
                    event_type,
                    dedupe_key,
                    status,
                    json.dumps(payload),
                ),
            )
        created = self.get_task(task_id)
        if created is None:
            raise RuntimeError("Failed to create task")
        return created

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return _row_to_task(row) if row else None

    def get_queued_task_for_repo(self, repo_key: str) -> TaskRecord | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tasks WHERE repo_key = ? AND status = 'queued' ORDER BY rowid ASC LIMIT 1",
                (repo_key,),
            ).fetchone()
        return _row_to_task(row) if row else None

    def claim_task(self, task_id: str, session_id: str, claimed_by: str, lease_expires_at: str) -> TaskRecord:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'claimed', session_id = ?, claimed_by = ?, lease_expires_at = ?, phase = 'context_prepared'
                WHERE task_id = ?
                """,
                (session_id, claimed_by, lease_expires_at, task_id),
            )
        task = self.get_task(task_id)
        if task is None:
            raise RuntimeError("Claimed task not found")
        return task

    def heartbeat_task(self, task_id: str, session_id: str, phase: str, lease_expires_at: str) -> TaskRecord:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'running', phase = ?, lease_expires_at = ?
                WHERE task_id = ? AND session_id = ?
                """,
                (phase, lease_expires_at, task_id, session_id),
            )
        task = self.get_task(task_id)
        if task is None:
            raise RuntimeError("Heartbeat task not found")
        return task

    def report_task(self, task_id: str, session_id: str, payload: dict) -> TaskRecord:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET status = 'reported', result_json = ?, summary = ?
                WHERE task_id = ? AND session_id = ?
                """,
                (json.dumps(payload), payload.get("summary"), task_id, session_id),
            )
        task = self.get_task(task_id)
        if task is None:
            raise RuntimeError("Reported task not found")
        return task

    def complete_task(self, task_id: str, reply_comment_id: int | None) -> TaskRecord:
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'completed', reply_comment_id = ? WHERE task_id = ?",
                (reply_comment_id, task_id),
            )
        task = self.get_task(task_id)
        if task is None:
            raise RuntimeError("Completed task not found")
        return task


def _row_to_task(row: sqlite3.Row) -> TaskRecord:
    return TaskRecord(
        task_id=row["task_id"],
        repo_key=row["repo_key"],
        issue_number=row["issue_number"],
        comment_id=row["comment_id"],
        event_type=row["event_type"],
        dedupe_key=row["dedupe_key"],
        status=row["status"],
        claimed_by=row["claimed_by"],
        session_id=row["session_id"],
        lease_expires_at=row["lease_expires_at"],
        phase=row["phase"],
        summary=row["summary"],
        payload_json=row["payload_json"],
        result_json=row["result_json"],
        reply_comment_id=row["reply_comment_id"],
    )
