from __future__ import annotations

import json
import os

import httpx


class SchedulerClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or os.environ.get("AGENT_SCHEDULER_URL", "http://127.0.0.1:8002")).rstrip("/")
        self._client = httpx.Client(timeout=30.0)

    def claim(self, payload: dict) -> dict | None:
        response = self._client.post(f"{self.base_url}/tasks/claim", json=payload)
        if response.status_code == 204:
            return None
        response.raise_for_status()
        return response.json()

    def heartbeat(self, payload: dict) -> dict:
        response = self._client.post(f"{self.base_url}/tasks/heartbeat", json=payload)
        response.raise_for_status()
        return response.json()

    def report(self, payload: dict) -> dict:
        response = self._client.post(f"{self.base_url}/tasks/report", json=payload)
        response.raise_for_status()
        return response.json()

    def release(self, payload: dict) -> dict:
        response = self._client.post(f"{self.base_url}/tasks/release", json=payload)
        response.raise_for_status()
        return response.json()


def dumps_pretty(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True)
