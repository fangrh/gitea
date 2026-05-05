# Agent Scheduler + Local Bridge Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an independent scheduler service plus a local bridge CLI/skill so Gitea issue/comment tasks are discovered remotely, executed locally in a checked-out repository, and reported back through a stable protocol.

**Architecture:** Add a new remote FastAPI service `agent-scheduler` that owns webhook ingestion, polling fallback, task state, leases, heartbeats, and Gitea replies. Add a local Python CLI `agent-bridge` that derives repository identity from `git remote origin`, claims tasks, maintains heartbeats, and reports terminal results. Wrap the CLI with a local Codex skill-oriented workflow instead of embedding agent execution into remote containers.

**Tech Stack:** Python 3.12, FastAPI, httpx, pydantic, sqlite/json file persistence for MVP, Docker Compose, pytest

---

## File Structure

### Remote scheduler service

- Create: `agent-services/scheduler/Dockerfile`
- Create: `agent-services/scheduler/requirements.txt`
- Create: `agent-services/scheduler/main.py`
- Create: `agent-services/scheduler/config.py`
- Create: `agent-services/scheduler/models.py`
- Create: `agent-services/scheduler/storage.py`
- Create: `agent-services/scheduler/repo_identity.py`
- Create: `agent-services/scheduler/gitea_client.py`
- Create: `agent-services/scheduler/task_detector.py`
- Create: `agent-services/scheduler/task_package.py`
- Create: `agent-services/scheduler/tests/test_repo_identity.py`
- Create: `agent-services/scheduler/tests/test_task_detector.py`
- Create: `agent-services/scheduler/tests/test_claim_api.py`
- Create: `agent-services/scheduler/tests/test_report_api.py`

### Local bridge CLI

- Create: `tools/agent_bridge/__init__.py`
- Create: `tools/agent_bridge/__main__.py`
- Create: `tools/agent_bridge/cli.py`
- Create: `tools/agent_bridge/repo_detect.py`
- Create: `tools/agent_bridge/client.py`
- Create: `tools/agent_bridge/heartbeat.py`
- Create: `tools/agent_bridge/result_schema.py`
- Create: `tools/agent_bridge/tests/test_repo_detect.py`
- Create: `tools/agent_bridge/tests/test_cli_claim.py`

### Skill and docs

- Create: `.agents/skills/agent-bridge/SKILL.md`
- Modify: `docker-compose.yml`
- Modify: `README.md`
- Create: `docs/agent-scheduler-local-bridge.md`

### Notes

- Keep scheduler code independent from `gds-services/` because this is not GDS-viewer-specific infrastructure.
- Use small focused modules. Do not put webhook logic, persistence, repo parsing, and Gitea reply logic into a single file.
- For MVP persistence, prefer a simple local sqlite DB under the scheduler container's writable data path instead of introducing Postgres or Redis.

---

## Chunk 1: Scheduler Service Skeleton and Repository Identity

### Task 1: Add scheduler service skeleton

**Files:**
- Create: `agent-services/scheduler/Dockerfile`
- Create: `agent-services/scheduler/requirements.txt`
- Create: `agent-services/scheduler/main.py`
- Modify: `docker-compose.yml`
- Test: `agent-services/scheduler/tests/test_health.py`

- [ ] **Step 1: Write the failing health test**

```python
from fastapi.testclient import TestClient

from main import app


def test_health() -> None:
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent-services/scheduler/tests/test_health.py -v`
Expected: FAIL with import or missing route error

- [ ] **Step 3: Write minimal FastAPI service**

```python
from fastapi import FastAPI

app = FastAPI(title="agent-scheduler")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

- [ ] **Step 4: Add Dockerfile and requirements**

Requirements:
- `fastapi`
- `uvicorn`
- `httpx`
- `pydantic`
- `pytest`

Dockerfile pattern should match existing `gds-services/*` Python services.

- [ ] **Step 5: Add scheduler service to Compose**

Add a new service:
- build context `./agent-services/scheduler`
- internal port `8002`
- writable volume for scheduler state under `/data/agent-scheduler`

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest agent-services/scheduler/tests/test_health.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add agent-services/scheduler docker-compose.yml
git commit -m "feat(agent-scheduler): add scheduler service skeleton"
```

### Task 2: Implement repository identity parsing

**Files:**
- Create: `agent-services/scheduler/repo_identity.py`
- Create: `agent-services/scheduler/tests/test_repo_identity.py`
- Create: `tools/agent_bridge/repo_detect.py`
- Create: `tools/agent_bridge/tests/test_repo_detect.py`

- [ ] **Step 1: Write failing scheduler-side parsing tests**

Cover:
- `ssh://git@localhost:2222/Owner/Repo.git`
- `git@localhost:Owner/Repo.git`
- `https://localhost/Owner/Repo.git`

Expected normalized object:

```python
{
    "repo_host": "localhost",
    "owner": "Owner",
    "repo": "Repo",
    "repo_key": "gitea://localhost/Owner/Repo",
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest agent-services/scheduler/tests/test_repo_identity.py -v`
Expected: FAIL because parser missing

- [ ] **Step 3: Implement shared parsing rules**

Scheduler-side parser should expose:
- `parse_remote_url(url: str) -> RepoIdentity`
- `repo_key(identity: RepoIdentity) -> str`

Local bridge should mirror the same rules in `tools/agent_bridge/repo_detect.py`.

- [ ] **Step 4: Write failing local bridge repo-detect tests**

Test:
- parse explicit remote string
- parse `git remote get-url origin` subprocess output

- [ ] **Step 5: Run both parser test files**

Run: `pytest agent-services/scheduler/tests/test_repo_identity.py tools/agent_bridge/tests/test_repo_detect.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent-services/scheduler/repo_identity.py agent-services/scheduler/tests/test_repo_identity.py tools/agent_bridge/repo_detect.py tools/agent_bridge/tests/test_repo_detect.py
git commit -m "feat(agent-bridge): normalize repository identity from git remotes"
```

---

## Chunk 2: Scheduler Storage, Task Detection, and Claim API

### Task 3: Add scheduler storage and task model

**Files:**
- Create: `agent-services/scheduler/models.py`
- Create: `agent-services/scheduler/storage.py`
- Create: `agent-services/scheduler/tests/test_storage.py`

- [ ] **Step 1: Write failing storage test for task lifecycle**

Test:
- create task in `queued`
- claim task
- heartbeat task
- mark `reported`
- mark `completed`

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent-services/scheduler/tests/test_storage.py -v`
Expected: FAIL because storage/model missing

- [ ] **Step 3: Define minimal task schema**

Required fields:
- `task_id`
- `repo_key`
- `issue_number`
- `comment_id`
- `event_type`
- `dedupe_key`
- `status`
- `claimed_by`
- `session_id`
- `lease_expires_at`
- `phase`
- `summary`

- [ ] **Step 4: Implement sqlite-backed storage**

Methods:
- `upsert_task(...)`
- `get_queued_task_for_repo(repo_key)`
- `claim_task(task_id, session_id, claimed_by, lease_expires_at)`
- `heartbeat_task(task_id, session_id, phase, lease_expires_at)`
- `report_task(task_id, session_id, payload)`
- `complete_task(task_id, reply_comment_id)`

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest agent-services/scheduler/tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent-services/scheduler/models.py agent-services/scheduler/storage.py agent-services/scheduler/tests/test_storage.py
git commit -m "feat(agent-scheduler): add task storage and lifecycle model"
```

### Task 4: Implement Gitea event detection rules

**Files:**
- Create: `agent-services/scheduler/gitea_client.py`
- Create: `agent-services/scheduler/task_detector.py`
- Create: `agent-services/scheduler/tests/test_task_detector.py`

- [ ] **Step 1: Write failing detector tests**

Cases:
- open `gds` issue with no agent resolution becomes a task
- new comment after latest agent reply becomes a task
- already-completed event does not create duplicate task

- [ ] **Step 2: Run detector tests to verify they fail**

Run: `pytest agent-services/scheduler/tests/test_task_detector.py -v`
Expected: FAIL because detector missing

- [ ] **Step 3: Implement minimal Gitea API client**

Methods:
- `get_issue(owner, repo, issue_number)`
- `list_issue_comments(owner, repo, issue_number)`
- `create_issue_comment(...)`
- `add_issue_labels(...)`
- `remove_issue_label(...)`

Use token auth and isolate HTTP concerns in this module only.

- [ ] **Step 4: Implement task detection logic**

Rules:
- task dedupe by `repo_key + issue_number + comment_id`
- comment tasks keyed by comment ID
- issue tasks keyed by issue number and unresolved state
- detect whether the agent already resolved using labels/task table instead of reply-only heuristics

- [ ] **Step 5: Run detector tests**

Run: `pytest agent-services/scheduler/tests/test_task_detector.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent-services/scheduler/gitea_client.py agent-services/scheduler/task_detector.py agent-services/scheduler/tests/test_task_detector.py
git commit -m "feat(agent-scheduler): detect unhandled issue and comment tasks"
```

### Task 5: Add claim API and task package response

**Files:**
- Modify: `agent-services/scheduler/main.py`
- Create: `agent-services/scheduler/task_package.py`
- Create: `agent-services/scheduler/tests/test_claim_api.py`

- [ ] **Step 1: Write failing claim API test**

Test:
- seed one queued task
- `POST /tasks/claim`
- assert 200
- assert task status becomes `claimed`
- assert response contains `task_id`, `repo`, `event`, `issue`, `context`

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent-services/scheduler/tests/test_claim_api.py -v`
Expected: FAIL because route missing

- [ ] **Step 3: Implement task package builder**

Package fields:
- `task_id`
- `repo.repo_key`
- `repo.clone_url`
- `repo.default_branch`
- `event.type`
- `event.issue_number`
- `event.comment_id`
- `event.comment_body`
- `issue.title`
- `issue.body`
- `provenance`
- `context.unreplied_reason`

- [ ] **Step 4: Implement `/tasks/claim`**

Behavior:
- accept `repo_key`, `agent_user`, `worker_host`, `session_id`
- atomically claim one queued task
- set lease expiration
- return full task package
- if none available, return `204 No Content`

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest agent-services/scheduler/tests/test_claim_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent-services/scheduler/main.py agent-services/scheduler/task_package.py agent-services/scheduler/tests/test_claim_api.py
git commit -m "feat(agent-scheduler): add claim API and task package responses"
```

---

## Chunk 3: Heartbeat, Report, and Gitea-visible State

### Task 6: Add heartbeat API and lease renewal

**Files:**
- Modify: `agent-services/scheduler/main.py`
- Modify: `agent-services/scheduler/storage.py`
- Create: `agent-services/scheduler/tests/test_heartbeat_api.py`

- [ ] **Step 1: Write failing heartbeat API test**

Test:
- claim a task
- send heartbeat with `phase="verifying"`
- assert lease moves forward
- assert phase updates

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent-services/scheduler/tests/test_heartbeat_api.py -v`
Expected: FAIL because route missing

- [ ] **Step 3: Implement `/tasks/heartbeat`**

Behavior:
- validate session ownership
- extend lease
- update phase and message
- keep task in `running`

- [ ] **Step 4: Run heartbeat test**

Run: `pytest agent-services/scheduler/tests/test_heartbeat_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent-services/scheduler/main.py agent-services/scheduler/storage.py agent-services/scheduler/tests/test_heartbeat_api.py
git commit -m "feat(agent-scheduler): add lease renewal heartbeat API"
```

### Task 7: Add report API and final reply handling

**Files:**
- Modify: `agent-services/scheduler/main.py`
- Modify: `agent-services/scheduler/gitea_client.py`
- Create: `agent-services/scheduler/tests/test_report_api.py`

- [ ] **Step 1: Write failing report API tests**

Cases:
- completed result posts final reply and marks task `completed`
- human-needed result posts clarification reply and marks `needs_human`

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest agent-services/scheduler/tests/test_report_api.py -v`
Expected: FAIL because report route missing

- [ ] **Step 3: Implement `/tasks/report`**

Accept payload fields:
- `task_id`
- `session_id`
- `status`
- `summary`
- `reply_body`
- `git.branch`
- `git.commit_sha`
- `git.pr_url`
- `build.status`
- `artifacts.changed_files`

- [ ] **Step 4: Implement finalization logic**

Behavior:
- verify active claim/session
- post reply comment using agent user credentials
- update visible labels:
  - `agent/done`
  - `agent/human-needed`
- persist final payload

- [ ] **Step 5: Run report tests**

Run: `pytest agent-services/scheduler/tests/test_report_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add agent-services/scheduler/main.py agent-services/scheduler/gitea_client.py agent-services/scheduler/tests/test_report_api.py
git commit -m "feat(agent-scheduler): add report API and final Gitea replies"
```

### Task 8: Add explicit release endpoint

**Files:**
- Modify: `agent-services/scheduler/main.py`
- Create: `agent-services/scheduler/tests/test_release_api.py`

- [ ] **Step 1: Write failing release test**

Test:
- claimed task
- release with reason
- task returns to `queued` or `needs_human` depending on release mode

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent-services/scheduler/tests/test_release_api.py -v`
Expected: FAIL because route missing

- [ ] **Step 3: Implement `/tasks/release`**

Minimal behavior for MVP:
- if user cancellation or local precondition failure, mark `queued` with release note
- if unsafe condition, allow `needs_human`

- [ ] **Step 4: Run release test**

Run: `pytest agent-services/scheduler/tests/test_release_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent-services/scheduler/main.py agent-services/scheduler/tests/test_release_api.py
git commit -m "feat(agent-scheduler): add explicit task release endpoint"
```

---

## Chunk 4: Webhook, Polling Fallback, and Visible Labels

### Task 9: Add webhook ingestion endpoint

**Files:**
- Modify: `agent-services/scheduler/main.py`
- Create: `agent-services/scheduler/tests/test_webhook_api.py`

- [ ] **Step 1: Write failing webhook test**

Test:
- send `issue_comment` webhook payload
- assert queued task created

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent-services/scheduler/tests/test_webhook_api.py -v`
Expected: FAIL because endpoint missing

- [ ] **Step 3: Implement `POST /events/gitea`**

Handle:
- `issues`
- `issue_comment`
- optional `push`

Ignore unrelated event types in MVP.

- [ ] **Step 4: Run webhook test**

Run: `pytest agent-services/scheduler/tests/test_webhook_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent-services/scheduler/main.py agent-services/scheduler/tests/test_webhook_api.py
git commit -m "feat(agent-scheduler): ingest Gitea issue and comment webhooks"
```

### Task 10: Add polling reconciliation endpoint

**Files:**
- Modify: `agent-services/scheduler/main.py`
- Create: `agent-services/scheduler/tests/test_reconcile_api.py`

- [ ] **Step 1: Write failing reconcile test**

Test:
- mocked Gitea state contains one untracked issue/comment
- `POST /poll/reconcile` creates task

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent-services/scheduler/tests/test_reconcile_api.py -v`
Expected: FAIL because route missing

- [ ] **Step 3: Implement reconciliation path**

Behavior:
- list open `gds` issues
- inspect comments
- create missing tasks using same detection logic as webhook

- [ ] **Step 4: Run reconcile test**

Run: `pytest agent-services/scheduler/tests/test_reconcile_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent-services/scheduler/main.py agent-services/scheduler/tests/test_reconcile_api.py
git commit -m "feat(agent-scheduler): add polling reconciliation endpoint"
```

### Task 11: Add label update behavior

**Files:**
- Modify: `agent-services/scheduler/gitea_client.py`
- Modify: `agent-services/scheduler/main.py`
- Create: `agent-services/scheduler/tests/test_labels.py`

- [ ] **Step 1: Write failing label tests**

Cases:
- queue task applies `agent/queued`
- claim/report transitions update labels

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest agent-services/scheduler/tests/test_labels.py -v`
Expected: FAIL because label helpers missing

- [ ] **Step 3: Implement label helpers**

Helpers:
- `ensure_status_label(issue_number, label_name)`
- `replace_status_label(issue_number, old_labels, new_label)`

- [ ] **Step 4: Run label tests**

Run: `pytest agent-services/scheduler/tests/test_labels.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add agent-services/scheduler/gitea_client.py agent-services/scheduler/main.py agent-services/scheduler/tests/test_labels.py
git commit -m "feat(agent-scheduler): update visible agent status labels"
```

---

## Chunk 5: Local Bridge CLI

### Task 12: Add bridge client and basic claim command

**Files:**
- Create: `tools/agent_bridge/client.py`
- Create: `tools/agent_bridge/cli.py`
- Create: `tools/agent_bridge/__main__.py`
- Create: `tools/agent_bridge/tests/test_cli_claim.py`

- [ ] **Step 1: Write failing CLI claim test**

Test:
- mock current repo remote
- mock scheduler `/tasks/claim`
- assert CLI prints task package JSON

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tools/agent_bridge/tests/test_cli_claim.py -v`
Expected: FAIL because CLI missing

- [ ] **Step 3: Implement scheduler client**

Methods:
- `claim(repo_key, agent_user, worker_host, session_id)`
- `heartbeat(...)`
- `report(...)`
- `release(...)`

- [ ] **Step 4: Implement `agent-bridge claim`**

Behavior:
- derive `repo_key` from current repo
- send claim request
- print returned task package JSON to stdout

- [ ] **Step 5: Run CLI test**

Run: `pytest tools/agent_bridge/tests/test_cli_claim.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/agent_bridge
git commit -m "feat(agent-bridge): add local claim CLI"
```

### Task 13: Add heartbeat helper process

**Files:**
- Create: `tools/agent_bridge/heartbeat.py`
- Create: `tools/agent_bridge/tests/test_heartbeat.py`

- [ ] **Step 1: Write failing heartbeat helper test**

Test:
- start helper with short interval
- assert client heartbeat called repeatedly until stop signal

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tools/agent_bridge/tests/test_heartbeat.py -v`
Expected: FAIL because helper missing

- [ ] **Step 3: Implement heartbeat loop**

Functions:
- `start_heartbeat(task_id, session_id, client, interval=60)`
- `stop_heartbeat(handle)`

- [ ] **Step 4: Run heartbeat helper test**

Run: `pytest tools/agent_bridge/tests/test_heartbeat.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/agent_bridge/heartbeat.py tools/agent_bridge/tests/test_heartbeat.py
git commit -m "feat(agent-bridge): add background heartbeat helper"
```

### Task 14: Add report and release commands

**Files:**
- Create: `tools/agent_bridge/result_schema.py`
- Modify: `tools/agent_bridge/cli.py`
- Create: `tools/agent_bridge/tests/test_cli_report.py`

- [ ] **Step 1: Write failing report CLI tests**

Cases:
- `report` reads `result.json` and posts it
- `release` sends a reason payload

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tools/agent_bridge/tests/test_cli_report.py -v`
Expected: FAIL because commands missing

- [ ] **Step 3: Implement result schema**

Validate:
- `task_id`
- `session_id`
- `status`
- `summary`
- `reply_body`
- `git`
- `build`
- `artifacts`

- [ ] **Step 4: Implement `report` and `release` commands**

Report usage:

```bash
python -m tools.agent_bridge report task_123 --file result.json
```

Release usage:

```bash
python -m tools.agent_bridge release task_123 --reason "local repo not clean"
```

- [ ] **Step 5: Run report CLI tests**

Run: `pytest tools/agent_bridge/tests/test_cli_report.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add tools/agent_bridge/result_schema.py tools/agent_bridge/cli.py tools/agent_bridge/tests/test_cli_report.py
git commit -m "feat(agent-bridge): add report and release commands"
```

---

## Chunk 6: Skill, Documentation, and End-to-End Verification

### Task 15: Write the local bridge skill

**Files:**
- Create: `.agents/skills/agent-bridge/SKILL.md`

- [ ] **Step 1: Draft skill workflow**

Skill must describe:
- claim a task from current repo
- inject task package into Codex context
- start heartbeat
- collect branch/commit/PR/build summary
- write result JSON
- report result

- [ ] **Step 2: Add concrete command examples**

Include:
- `python -m tools.agent_bridge claim`
- `python -m tools.agent_bridge report ...`
- `python -m tools.agent_bridge release ...`

- [ ] **Step 3: Commit**

```bash
git add .agents/skills/agent-bridge/SKILL.md
git commit -m "feat(skill): add local agent bridge skill"
```

### Task 16: Document service and operator workflow

**Files:**
- Create: `docs/agent-scheduler-local-bridge.md`
- Modify: `README.md`

- [ ] **Step 1: Write usage guide**

Document:
- scheduler service purpose
- environment variables
- webhook setup
- polling fallback
- local CLI usage
- long-task heartbeat behavior

- [ ] **Step 2: Add README pointer**

Add a short section linking to the detailed doc.

- [ ] **Step 3: Commit**

```bash
git add docs/agent-scheduler-local-bridge.md README.md
git commit -m "docs: add scheduler and local bridge usage guide"
```

### Task 17: End-to-end verification

**Files:**
- No source changes required unless defects are found

- [ ] **Step 1: Run scheduler unit tests**

Run:

```bash
pytest agent-services/scheduler/tests -v
```

Expected: all PASS

- [ ] **Step 2: Run bridge unit tests**

Run:

```bash
pytest tools/agent_bridge/tests -v
```

Expected: all PASS

- [ ] **Step 3: Build scheduler container**

Run:

```bash
docker compose up -d --build agent-scheduler
```

Expected: service starts and `/health` returns `{"status":"ok"}`

- [ ] **Step 4: Smoke test claim/report path**

Manual flow:
- create or select a test `gds` issue/comment
- trigger webhook or run reconciliation
- from a local repo run `agent-bridge claim`
- send a sample report payload
- verify scheduler posts comment and updates labels

- [ ] **Step 5: Fix any defects found**

If a test or smoke check fails, return to the relevant task and add a targeted failing test before patching.

- [ ] **Step 6: Final commit**

```bash
git add .
git commit -m "feat(agent): deliver scheduler and local bridge MVP"
```

---

## Execution Notes

- Follow `@superpowers:test-driven-development` for every new route and module.
- Keep scheduler protocol narrow. Do not let the skill reimplement business rules from the scheduler.
- Do not embed remote agent execution into the scheduler or worker in this MVP.
- Do not modify Gitea core unless a truly blocking limitation is discovered.
- If repository-specific preprocessing becomes heavy later, split the logical worker into a real ephemeral container in a follow-up plan.

Plan complete and saved to `docs/superpowers/plans/2026-05-05-agent-scheduler-local-bridge-implementation.md`. Ready to execute?
