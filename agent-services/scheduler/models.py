from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TaskRecord:
    task_id: str
    repo_key: str
    issue_number: int | None
    comment_id: int | None
    event_type: str
    dedupe_key: str
    status: str
    claimed_by: str | None = None
    session_id: str | None = None
    lease_expires_at: str | None = None
    phase: str | None = None
    summary: str | None = None
    payload_json: str | None = None
    result_json: str | None = None
    reply_comment_id: int | None = None
