from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


def test_heartbeat_updates_phase_and_lease(tmp_path: Path) -> None:
    main.storage = main.SchedulerStorage(tmp_path / "scheduler.db")
    task = main.storage.upsert_task(
        repo_key="gitea://localhost/Owner/Repo",
        issue_number=1,
        comment_id=None,
        event_type="issue",
        dedupe_key="issue:1",
        payload={},
    )
    main.storage.claim_task(task.task_id, "session-1", "agent", "2026-05-05T12:00:00Z")
    client = TestClient(main.app)
    response = client.post(
        "/tasks/heartbeat",
        json={"task_id": task.task_id, "session_id": "session-1", "phase": "verifying", "message": "running tests"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "running"
    assert body["phase"] == "verifying"
