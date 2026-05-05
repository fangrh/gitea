from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from gitea_client import GiteaClient


def test_webhook_creates_comment_task(tmp_path: Path) -> None:
    main.storage = main.SchedulerStorage(tmp_path / "scheduler.db")
    main.gitea_client = GiteaClient()
    client = TestClient(main.app)
    response = client.post(
        "/events/gitea",
        json={
            "event_type": "issue_comment",
            "repo_key": "gitea://localhost/Owner/Repo",
            "issue": {"number": 17, "state": "open", "labels": ["gds"], "title": "T"},
            "comment": {"id": 203, "body": "please fix", "user": {"login": "alice"}},
        },
    )
    assert response.status_code == 200
    assert response.json()["created"] == 1
    task = main.storage.get_queued_task_for_repo("gitea://localhost/Owner/Repo")
    assert task is not None
    assert task.comment_id == 203
