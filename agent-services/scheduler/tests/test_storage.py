from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from storage import SchedulerStorage


def test_task_lifecycle(tmp_path: Path) -> None:
    storage = SchedulerStorage(tmp_path / "scheduler.db")
    task = storage.upsert_task(
        repo_key="gitea://localhost/Owner/Repo",
        issue_number=1,
        comment_id=None,
        event_type="issue",
        dedupe_key="issue:1",
        payload={"hello": "world"},
    )
    assert task.status == "queued"

    queued = storage.get_queued_task_for_repo("gitea://localhost/Owner/Repo")
    assert queued is not None
    assert queued.task_id == task.task_id

    claimed = storage.claim_task(task.task_id, "session-1", "agent", "2026-05-05T12:00:00Z")
    assert claimed.status == "claimed"
    assert claimed.session_id == "session-1"

    running = storage.heartbeat_task(task.task_id, "session-1", "verifying", "2026-05-05T12:01:00Z")
    assert running.status == "running"
    assert running.phase == "verifying"

    reported = storage.report_task(task.task_id, "session-1", {"summary": "done"})
    assert reported.status == "reported"
    assert reported.summary == "done"

    completed = storage.complete_task(task.task_id, 12)
    assert completed.status == "completed"
    assert completed.reply_comment_id == 12
