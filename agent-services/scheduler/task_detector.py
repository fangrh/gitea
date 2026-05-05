from __future__ import annotations


def issue_task_payload(repo_key: str, issue: dict) -> dict:
    return {
        "repo": {"repo_key": repo_key},
        "event": {"type": "issue", "issue_number": issue["number"]},
        "issue": {"title": issue.get("title", ""), "body": issue.get("body", ""), "labels": issue.get("labels", [])},
        "provenance": issue.get("provenance", {}),
        "context": {"unreplied_reason": "open_gds_issue"},
    }


def comment_task_payload(repo_key: str, issue: dict, comment: dict) -> dict:
    return {
        "repo": {"repo_key": repo_key},
        "event": {
            "type": "issue_comment",
            "issue_number": issue["number"],
            "comment_id": comment["id"],
            "comment_author": comment.get("user", {}).get("login", ""),
            "comment_body": comment.get("body", ""),
        },
        "issue": {"title": issue.get("title", ""), "body": issue.get("body", ""), "labels": issue.get("labels", [])},
        "provenance": issue.get("provenance", {}),
        "context": {"unreplied_reason": "new_comment_after_last_agent_reply"},
    }


def should_create_issue_task(issue: dict) -> bool:
    return issue.get("state", "open") == "open" and "gds" in issue.get("labels", [])


def should_create_comment_task(issue: dict, comment: dict) -> bool:
    if not should_create_issue_task(issue):
        return False
    return comment.get("user", {}).get("login") != "gds-agent"
