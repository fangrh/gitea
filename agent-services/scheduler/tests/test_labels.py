from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from gitea_client import GiteaClient


def test_claim_and_report_update_status_labels(tmp_path: Path) -> None:
    main.storage = main.SchedulerStorage(tmp_path / "scheduler.db")
    main.gitea_client = GiteaClient()
    main.storage.upsert_task(
        repo_key="gitea://localhost/Owner/Repo",
        issue_number=17,
        comment_id=None,
        event_type="issue",
        dedupe_key="issue:17",
        payload={},
    )
    client = TestClient(main.app)
    claim = client.post(
        "/tasks/claim",
        json={
            "repo_key": "gitea://localhost/Owner/Repo",
            "agent_user": "gds-agent",
            "worker_host": "local",
            "session_id": "session-1",
        },
    )
    task_id = claim.json()["task_id"]
    done = client.post(
        "/tasks/report",
        json={
            "task_id": task_id,
            "session_id": "session-1",
            "status": "completed",
            "summary": "done",
            "reply_body": "done",
            "git": {},
            "build": {},
            "artifacts": {},
        },
    )
    assert done.status_code == 200
    assert main.gitea_client.labels[-1] == (17, "agent/done")
