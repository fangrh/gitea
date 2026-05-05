from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "agent-services" / "scheduler"))
from repo_identity import RepoIdentity, parse_remote_url  # noqa: F401
