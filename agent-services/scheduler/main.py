from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel

from config import get_settings
from gitea_client import GiteaClient
from storage import SchedulerStorage
from task_detector import (
    comment_task_payload,
    issue_task_payload,
    should_create_comment_task,
    should_create_issue_task,
)
from task_package import build_task_package

app = FastAPI(title="agent-scheduler")
settings = get_settings()
storage = SchedulerStorage(settings.db_path)
gitea_client = GiteaClient()


class ClaimRequest(BaseModel):
    repo_key: str
    agent_user: str
    worker_host: str
    session_id: str


class HeartbeatRequest(BaseModel):
    task_id: str
    session_id: str
    phase: str
    message: str | None = None


class ReportRequest(BaseModel):
    task_id: str
    session_id: str
    status: str
    summary: str
    reply_body: str
    git: dict | None = None
    build: dict | None = None
    artifacts: dict | None = None


class ReleaseRequest(BaseModel):
    task_id: str
    session_id: str
    reason: str
    status: str = "queued"


class ReconcileRequest(BaseModel):
    repo_key: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/events/gitea")
def ingest_gitea_event(payload: dict) -> dict:
    event_type = payload.get("event_type")
    repo_key = payload.get("repo_key")
    created = 0
    if event_type == "issues":
        issue = payload.get("issue", {})
        if repo_key and should_create_issue_task(issue):
            storage.upsert_task(
                repo_key=repo_key,
                issue_number=issue["number"],
                comment_id=None,
                event_type="issue",
                dedupe_key=f"issue:{repo_key}:{issue['number']}",
                payload=issue_task_payload(repo_key, issue),
            )
            gitea_client.replace_status_label(issue["number"], "agent/queued")
            created += 1
    elif event_type == "issue_comment":
        issue = payload.get("issue", {})
        comment = payload.get("comment", {})
        if repo_key and should_create_comment_task(issue, comment):
            storage.upsert_task(
                repo_key=repo_key,
                issue_number=issue["number"],
                comment_id=comment["id"],
                event_type="issue_comment",
                dedupe_key=f"comment:{repo_key}:{comment['id']}",
                payload=comment_task_payload(repo_key, issue, comment),
            )
            gitea_client.replace_status_label(issue["number"], "agent/queued")
            created += 1
    return {"created": created}


@app.post("/poll/reconcile")
def reconcile(request: ReconcileRequest) -> dict:
    created = 0
    for issue in gitea_client.list_gds_issues():
        if should_create_issue_task(issue):
            before = storage.upsert_task(
                repo_key=request.repo_key,
                issue_number=issue["number"],
                comment_id=None,
                event_type="issue",
                dedupe_key=f"issue:{request.repo_key}:{issue['number']}",
                payload=issue_task_payload(request.repo_key, issue),
            )
            if before:
                gitea_client.replace_status_label(issue["number"], "agent/queued")
            created += 1
        for comment in gitea_client.list_issue_comments(issue["number"]):
            if should_create_comment_task(issue, comment):
                storage.upsert_task(
                    repo_key=request.repo_key,
                    issue_number=issue["number"],
                    comment_id=comment["id"],
                    event_type="issue_comment",
                    dedupe_key=f"comment:{request.repo_key}:{comment['id']}",
                    payload=comment_task_payload(request.repo_key, issue, comment),
                )
                gitea_client.replace_status_label(issue["number"], "agent/queued")
                created += 1
    return {"created": created}


@app.post("/tasks/claim")
def claim_task(request: ClaimRequest, response: Response):
    task = storage.get_queued_task_for_repo(request.repo_key)
    if task is None:
        response.status_code = 204
        return None
    claimed = storage.claim_task(
        task.task_id,
        request.session_id,
        request.agent_user,
        _lease_expiry(),
    )
    if claimed.issue_number is not None:
        gitea_client.replace_status_label(claimed.issue_number, "agent/running")
    return build_task_package(claimed)


@app.post("/tasks/heartbeat")
def heartbeat_task(request: HeartbeatRequest) -> dict:
    task = storage.get_task(request.task_id)
    if task is None or task.session_id != request.session_id:
        raise HTTPException(status_code=404, detail="Task not claimed by session")
    updated = storage.heartbeat_task(request.task_id, request.session_id, request.phase, _lease_expiry())
    return {
        "task_id": updated.task_id,
        "status": updated.status,
        "phase": updated.phase,
        "lease_expires_at": updated.lease_expires_at,
    }


@app.post("/tasks/report")
def report_task(request: ReportRequest) -> dict:
    task = storage.get_task(request.task_id)
    if task is None or task.session_id != request.session_id:
        raise HTTPException(status_code=404, detail="Task not claimed by session")
    payload = request.model_dump()
    reported = storage.report_task(request.task_id, request.session_id, payload)
    reply = gitea_client.create_issue_comment(reported.issue_number or 0, request.reply_body)
    if request.status == "completed":
        completed = storage.complete_task(reported.task_id, int(reply["id"]))
        if completed.issue_number is not None:
            gitea_client.replace_status_label(completed.issue_number, "agent/done")
        return {"task_id": completed.task_id, "status": completed.status, "reply_comment_id": completed.reply_comment_id}
    released = storage.release_task(reported.task_id, request.session_id, "needs_human", request.summary)
    if released.issue_number is not None:
        gitea_client.replace_status_label(released.issue_number, "agent/human-needed")
    return {"task_id": released.task_id, "status": released.status}


@app.post("/tasks/release")
def release_task(request: ReleaseRequest) -> dict:
    task = storage.get_task(request.task_id)
    if task is None or task.session_id != request.session_id:
        raise HTTPException(status_code=404, detail="Task not claimed by session")
    updated = storage.release_task(request.task_id, request.session_id, request.status, request.reason)
    if updated.issue_number is not None:
        label = "agent/queued" if updated.status == "queued" else "agent/human-needed"
        gitea_client.replace_status_label(updated.issue_number, label)
    return {"task_id": updated.task_id, "status": updated.status, "summary": updated.summary}


def _lease_expiry() -> str:
    return (datetime.now(UTC) + timedelta(seconds=settings.lease_seconds)).isoformat()
