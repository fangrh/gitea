from __future__ import annotations

import json

from models import TaskRecord


def build_task_package(task: TaskRecord) -> dict:
    payload = json.loads(task.payload_json or "{}")
    return {
        "task_id": task.task_id,
        "repo": payload.get("repo", {"repo_key": task.repo_key}),
        "event": payload.get("event", {}),
        "issue": payload.get("issue", {}),
        "provenance": payload.get("provenance", {}),
        "context": payload.get("context", {}),
    }
