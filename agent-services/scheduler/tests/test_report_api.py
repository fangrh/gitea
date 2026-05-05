from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from gitea_client import GiteaClient


def test_report_completed_marks_task_done(tmp_path: Path) -> None:
    main.storage = main.SchedulerStorage(tmp_path / "scheduler.db")
    main.gitea_client = GiteaClient()
    task = main.storage.upsert_task(
        repo_key="gitea://localhost/Owner/Repo",
        issue_number=17,
        comment_id=None,
        event_type="issue",
        dedupe_key="issue:17",
        payload={},
    )
    main.storage.claim_task(task.task_id, "session-1", "agent", "2026-05-05T12:00:00Z")
    client = TestClient(main.app)
    response = client.post(
        "/tasks/report",
        json={
            "task_id": task.task_id,
            "session_id": "session-1",
            "status": "completed",
            "summary": "done",
            "reply_body": "Automated fix applied",
            "git": {"branch": "fix/x"},
            "build": {"status": "passed"},
            "artifacts": {"changed_files": ["a.py"]},
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_report_human_needed_marks_task_needs_human(tmp_path: Path) -> None:
    main.storage = main.SchedulerStorage(tmp_path / "scheduler.db")
    main.gitea_client = GiteaClient()
    task = main.storage.upsert_task(
        repo_key="gitea://localhost/Owner/Repo",
        issue_number=18,
        comment_id=None,
        event_type="issue",
        dedupe_key="issue:18",
        payload={},
    )
    main.storage.claim_task(task.task_id, "session-2", "agent", "2026-05-05T12:00:00Z")
    client = TestClient(main.app)
    response = client.post(
        "/tasks/report",
        json={
            "task_id": task.task_id,
            "session_id": "session-2",
            "status": "needs_human",
            "summary": "ambiguous",
            "reply_body": "Need clarification",
            "git": {},
            "build": {"status": "not_run"},
            "artifacts": {},
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "needs_human"
