from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GiteaClient:
    comments: list[tuple[int, str]] = field(default_factory=list)
    labels: list[tuple[int, str]] = field(default_factory=list)
    issues: list[dict] = field(default_factory=list)
    issue_comments: dict[int, list[dict]] = field(default_factory=dict)

    def create_issue_comment(self, issue_number: int, body: str) -> dict:
        self.comments.append((issue_number, body))
        return {"id": len(self.comments), "issue_number": issue_number, "body": body}

    def add_issue_label(self, issue_number: int, label: str) -> None:
        self.labels.append((issue_number, label))

    def replace_status_label(self, issue_number: int, label: str) -> None:
        self.labels = [entry for entry in self.labels if entry[0] != issue_number]
        self.labels.append((issue_number, label))

    def list_gds_issues(self) -> list[dict]:
        return [issue for issue in self.issues if issue.get("state", "open") == "open" and "gds" in issue.get("labels", [])]

    def list_issue_comments(self, issue_number: int) -> list[dict]:
        return self.issue_comments.get(issue_number, [])
