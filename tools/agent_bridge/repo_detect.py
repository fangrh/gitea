from __future__ import annotations

import subprocess

from agent_services_repo_identity import parse_remote_url


def detect_from_remote_url(url: str) -> dict[str, str]:
    return parse_remote_url(url).to_dict()


def detect_from_git_remote() -> dict[str, str]:
    result = subprocess.run(
        ["git", "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        check=True,
    )
    return detect_from_remote_url(result.stdout.strip())
