from __future__ import annotations

from dataclasses import dataclass, asdict
from urllib.parse import urlparse
import re


@dataclass(frozen=True)
class RepoIdentity:
    repo_url: str
    repo_host: str
    owner: str
    repo: str

    @property
    def repo_key(self) -> str:
        return f"gitea://{self.repo_host}/{self.owner}/{self.repo}"

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        data["repo_key"] = self.repo_key
        return data


_SCP_RE = re.compile(r"^(?P<user>[^@]+)@(?P<host>[^:]+):(?P<owner>[^/]+)/(?P<repo>[^/]+?)(?:\.git)?$")


def parse_remote_url(url: str) -> RepoIdentity:
    if "://" in url:
        parsed = urlparse(url)
        path = parsed.path.lstrip("/")
        parts = path.split("/")
        if len(parts) < 2:
            raise ValueError(f"Unsupported remote URL: {url}")
        owner, repo = parts[0], parts[1]
        if repo.endswith(".git"):
            repo = repo[:-4]
        return RepoIdentity(repo_url=url, repo_host=parsed.hostname or "", owner=owner, repo=repo)

    match = _SCP_RE.match(url)
    if match:
        repo = match.group("repo")
        if repo.endswith(".git"):
            repo = repo[:-4]
        return RepoIdentity(
            repo_url=url,
            repo_host=match.group("host"),
            owner=match.group("owner"),
            repo=repo,
        )

    raise ValueError(f"Unsupported remote URL: {url}")
