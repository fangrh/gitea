from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    storage_dir: Path
    db_path: Path
    lease_seconds: int = 1800


def get_settings() -> Settings:
    storage_dir = Path(os.environ.get("AGENT_SCHEDULER_DATA_DIR", "/data/agent-scheduler"))
    return Settings(
        storage_dir=storage_dir,
        db_path=storage_dir / "scheduler.db",
    )
