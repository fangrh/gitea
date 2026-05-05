from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from task_detector import should_create_comment_task, should_create_issue_task


def test_open_gds_issue_creates_task() -> None:
    assert should_create_issue_task({"number": 1, "state": "open", "labels": ["gds"]}) is True


def test_non_gds_issue_does_not_create_task() -> None:
    assert should_create_issue_task({"number": 1, "state": "open", "labels": ["bug"]}) is False


def test_non_agent_comment_creates_followup_task() -> None:
    issue = {"number": 1, "state": "open", "labels": ["gds"]}
    comment = {"id": 2, "user": {"login": "alice"}}
    assert should_create_comment_task(issue, comment) is True
