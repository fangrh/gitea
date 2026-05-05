from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from client import SchedulerClient


@dataclass
class HeartbeatHandle:
    stop_event: threading.Event
    thread: threading.Thread


def start_heartbeat(
    task_id: str,
    session_id: str,
    client: SchedulerClient,
    interval: float = 60.0,
    phase: str = "running",
) -> HeartbeatHandle:
    stop_event = threading.Event()

    def _loop() -> None:
        while not stop_event.wait(interval):
            client.heartbeat(
                {
                    "task_id": task_id,
                    "session_id": session_id,
                    "phase": phase,
                    "message": "",
                }
            )

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return HeartbeatHandle(stop_event=stop_event, thread=thread)


def stop_heartbeat(handle: HeartbeatHandle) -> None:
    handle.stop_event.set()
    handle.thread.join(timeout=1.0)
