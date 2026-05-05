from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "agent-services" / "scheduler"))
sys.path.insert(0, str(ROOT / "tools" / "agent_bridge"))

from repo_detect import detect_from_remote_url


def test_detect_from_remote_url() -> None:
    data = detect_from_remote_url("git@localhost:Owner/Repo.git")
    assert data["repo_key"] == "gitea://localhost/Owner/Repo"
