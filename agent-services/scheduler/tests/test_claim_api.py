from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main


def test_claim_api_returns_task_package(tmp_path: Path) -> None:
    main.storage = main.SchedulerStorage(tmp_path / "scheduler.db")
    main.storage.upsert_task(
        repo_key="gitea://localhost/Owner/Repo",
        issue_number=17,
        comment_id=203,
        event_type="issue_comment",
        dedupe_key="comment:203",
        payload={
            "repo": {"repo_key": "gitea://localhost/Owner/Repo", "clone_url": "ssh://git@localhost:2222/Owner/Repo.git"},
            "event": {"type": "issue_comment", "issue_number": 17, "comment_id": 203},
            "issue": {"title": "MZI output mismatch"},
            "context": {"unreplied_reason": "new_comment_after_last_agent_reply"},
        },
    )
    client = TestClient(main.app)
    response = client.post(
        "/tasks/claim",
        json={
            "repo_key": "gitea://localhost/Owner/Repo",
            "agent_user": "gds-agent",
            "worker_host": "local",
            "session_id": "session-1",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["repo"]["repo_key"] == "gitea://localhost/Owner/Repo"
    assert body["event"]["comment_id"] == 203
