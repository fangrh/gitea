from __future__ import annotations

from fastapi import FastAPI

from config import get_settings
from storage import SchedulerStorage

app = FastAPI(title="agent-scheduler")
settings = get_settings()
storage = SchedulerStorage(settings.db_path)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
