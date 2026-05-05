from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "agent_bridge"))

import cli


class FakeClient:
    def __init__(self) -> None:
        self.payload = None

    def claim(self, payload: dict) -> dict:
        self.payload = payload
        return {"task_id": "task_123", "repo": {"repo_key": payload["repo_key"]}}


def test_claim_prints_task_package(monkeypatch, capsys) -> None:
    fake = FakeClient()
    monkeypatch.setattr(cli, "SchedulerClient", lambda: fake)
    monkeypatch.setattr(
        cli,
        "detect_from_git_remote",
        lambda: {"repo_key": "gitea://localhost/Owner/Repo"},
    )
    rc = cli.main(["claim"])
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out)["task_id"] == "task_123"
    assert fake.payload["repo_key"] == "gitea://localhost/Owner/Repo"
