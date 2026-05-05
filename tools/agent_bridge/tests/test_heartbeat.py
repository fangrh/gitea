from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools" / "agent_bridge"))

from heartbeat import start_heartbeat, stop_heartbeat


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def heartbeat(self, payload: dict) -> dict:
        self.calls += 1
        return payload


def test_heartbeat_repeats_until_stopped() -> None:
    client = FakeClient()
    handle = start_heartbeat("task_1", "sess", client, interval=0.01, phase="verifying")
    time.sleep(0.05)
    stop_heartbeat(handle)
    assert client.calls >= 2
