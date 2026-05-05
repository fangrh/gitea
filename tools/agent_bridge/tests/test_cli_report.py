from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "agent_bridge"))

import cli


class FakeClient:
    def __init__(self) -> None:
        self.report_payload = None
        self.release_payload = None

    def report(self, payload: dict) -> dict:
        self.report_payload = payload
        return {"status": "completed"}

    def release(self, payload: dict) -> dict:
        self.release_payload = payload
        return {"status": payload["status"]}


def test_report_reads_result_file(monkeypatch, tmp_path: Path, capsys) -> None:
    fake = FakeClient()
    monkeypatch.setattr(cli, "SchedulerClient", lambda: fake)
    result_file = tmp_path / "result.json"
    result_file.write_text(
        json.dumps({"status": "completed", "summary": "done", "reply_body": "ok", "git": {}, "build": {}, "artifacts": {}}),
        encoding="utf-8",
    )
    rc = cli.main(["report", "task_1", "--session-id", "sess", "--file", str(result_file)])
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out)["status"] == "completed"
    assert fake.report_payload["task_id"] == "task_1"


def test_release_posts_reason(monkeypatch, capsys) -> None:
    fake = FakeClient()
    monkeypatch.setattr(cli, "SchedulerClient", lambda: fake)
    rc = cli.main(["release", "task_1", "--session-id", "sess", "--reason", "repo dirty"])
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out)["status"] == "queued"
    assert fake.release_payload["reason"] == "repo dirty"
