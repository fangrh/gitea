from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import main
from gitea_client import GiteaClient


def test_reconcile_creates_missing_tasks(tmp_path: Path) -> None:
    main.storage = main.SchedulerStorage(tmp_path / "scheduler.db")
    main.gitea_client = GiteaClient(
        issues=[{"number": 7, "state": "open", "labels": ["gds"], "title": "Issue"}],
        issue_comments={7: [{"id": 99, "body": "follow up", "user": {"login": "alice"}}]},
    )
    client = TestClient(main.app)
    response = client.post("/poll/reconcile", json={"repo_key": "gitea://localhost/Owner/Repo"})
    assert response.status_code == 200
    assert response.json()["created"] >= 1
    task = main.storage.get_queued_task_for_repo("gitea://localhost/Owner/Repo")
    assert task is not None
