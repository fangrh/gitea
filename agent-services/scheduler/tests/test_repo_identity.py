from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repo_identity import parse_remote_url


def test_parse_ssh_url() -> None:
    identity = parse_remote_url("ssh://git@localhost:2222/Owner/Repo.git")
    assert identity.to_dict() == {
        "repo_url": "ssh://git@localhost:2222/Owner/Repo.git",
        "repo_host": "localhost",
        "owner": "Owner",
        "repo": "Repo",
        "repo_key": "gitea://localhost/Owner/Repo",
    }


def test_parse_scp_url() -> None:
    identity = parse_remote_url("git@localhost:Owner/Repo.git")
    assert identity.to_dict()["repo_key"] == "gitea://localhost/Owner/Repo"


def test_parse_https_url() -> None:
    identity = parse_remote_url("https://localhost/Owner/Repo.git")
    assert identity.to_dict()["repo_key"] == "gitea://localhost/Owner/Repo"
