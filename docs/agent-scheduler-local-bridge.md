# Agent Scheduler and Local Bridge

This repository includes an MVP remote scheduler plus a local bridge CLI for processing repository-scoped Gitea issue/comment tasks.

## Components

- `agent-scheduler`
  - remote FastAPI service
  - owns task state, leases, heartbeats, and final replies
- `tools.agent_bridge`
  - local CLI used inside a checked-out repository
  - claims tasks, sends heartbeats, reports results, and releases tasks

## Scheduler Service

Run:

```bash
docker compose up -d --build agent-scheduler
```

Health check:

```bash
curl http://127.0.0.1:8002/health
```

Expected:

```json
{"status":"ok"}
```

The scheduler stores its sqlite database under `/data/agent-scheduler/scheduler.db` inside the container.

## Local Bridge CLI

Claim the next task for the current repository:

```bash
python -m tools.agent_bridge claim
```

Send heartbeat:

```bash
python -m tools.agent_bridge heartbeat <task_id> --session-id <session_id> --phase verifying --message "running snakemake"
```

Report completion:

```bash
python -m tools.agent_bridge report <task_id> --session-id <session_id> --file result.json
```

Release a task:

```bash
python -m tools.agent_bridge release <task_id> --session-id <session_id> --reason "local repo not clean"
```

## Result Payload

`result.json` should contain at least:

```json
{
  "status": "completed",
  "summary": "Adjusted output straight width and verified build.",
  "reply_body": "Automated fix applied: ...",
  "git": {
    "branch": "fix/17-output-width",
    "commit_sha": "abc123",
    "pr_url": "http://localhost:3000/owner/repo/pulls/9"
  },
  "build": {
    "status": "passed",
    "command": "snakemake --cores 4",
    "log_excerpt": "..."
  },
  "artifacts": {
    "changed_files": ["designs/example_mzi.py"]
  }
}
```

## Long-Running Tasks

Tasks may take a long time because local agent execution includes code changes and validation. Use heartbeat updates during long-running sessions so the scheduler lease stays valid.

## Scope

The current implementation is intentionally small:

- webhook/polling ingestion
- scheduler claim/heartbeat/report/release APIs
- repository-scoped local bridge CLI
- local skill wrapper

Future work can add:

- stronger Gitea authentication
- more detailed reconciliation rules
- a global inbox command
- true ephemeral worker containers if preprocessing becomes heavy
