# Agent Scheduler + Local Bridge Design

**Date:** 2026-05-05

**Goal:** Build a maintainable agent communication system for Gitea-backed design repositories where a remote scheduler discovers unhandled issues/comments, a local Codex session performs the actual work inside the user's checked-out repository, and the system reports results back using the agent user.

**Non-Goal:** Do not embed full agent execution into Gitea or into a remote worker container. The remote side should coordinate and package work, but the real coding and validation loop stays in the user's local repository session.

## Problem

Current behavior mixes Gitea-facing communication concerns with execution concerns too tightly:

- repository discovery depends on remote URL knowledge but is not cleanly exposed as a stable task interface
- issue/comment polling, reply detection, and execution workflow are coupled in ways that are harder to maintain
- local repository use is not packaged as a simple reusable skill/CLI workflow
- long-running agent work needs explicit task ownership, lease renewal, and final resolution semantics

The system needs a clean separation between:

- Gitea integration
- task scheduling and state tracking
- local repository execution
- reusable skill/CLI ergonomics

## Chosen Architecture

Use a **scheduler + local bridge** architecture, preserving the logical worker boundary but not requiring a separate worker container in the MVP.

### Components

#### 1. `gitea`

Provides:

- repository hosting
- issue/comment/PR API
- webhook source
- authentication and agent user identity

Does not own:

- agent task state machine
- lease and heartbeat logic
- local execution workflow

#### 2. `agent-scheduler` container

Single remote control-plane service.

Responsibilities:

- receive Gitea webhooks
- run polling fallback
- normalize repository identity from SSH/HTTP remotes
- create and deduplicate tasks for issues/comments
- maintain authoritative task state
- expose claim/heartbeat/report/release API for local clients
- apply lightweight visible status back into Gitea
- post final replies using the agent user

#### 3. Logical `worker` boundary

The architecture retains a worker concept for task packaging, but in the MVP this should remain an internal scheduler module, not a separate deployed container.

Responsibilities:

- gather event payload, issue/comment body, provenance, and reply context
- assemble a standard task package for local consumption

This can later be split into ephemeral containers if repository-specific preprocessing becomes heavy or isolation requirements increase.

#### 4. `local-bridge`

Thin local communication layer used from inside a checked-out repository.

Responsibilities:

- inspect `git remote origin`
- derive stable repository identity
- claim a task for the current repository
- keep the task alive with heartbeats during long execution
- report final result package back to the scheduler

This is the basis for both a local CLI and a Codex skill.

## Why This Architecture

This architecture was chosen over a monolithic Gitea-integrated automation service because:

- Gitea should remain a forge and event source, not an execution orchestrator
- scheduler logic will evolve faster than Gitea platform code
- failures in task orchestration should not expand Gitea's fault domain
- the real agent workflow already happens locally in a repository session and should remain there
- local skill ergonomics become much simpler if remote coordination is reduced to a narrow task API

## Repository Identity Model

The stable key is derived from the remote repository identity, not from local filesystem paths.

Fields:

- `repo_url`
- `repo_host`
- `owner`
- `repo`
- `repo_key`

Recommended canonical key:

```text
gitea://<host>/<owner>/<repo>
```

Examples:

```text
gitea://localhost/RuihuanFang/phononic-superconductor
gitea://git.example.com/team/project
```

This lets multiple local clones of the same repository claim from the same logical queue.

## Event Ingestion

Use **webhook as primary** and **polling as fallback**.

### Webhook

Primary low-latency path for:

- issue opened/edited
- issue comment created
- optional push events

### Polling

Fallback reconciliation path for:

- webhook delivery failures
- scheduler downtime recovery
- missed or reordered events

Polling should not be the main path, only a compensating mechanism.

## Task Detection Rules

The scheduler decides whether an issue/comment becomes a task.

### Default rules

- open issue labeled `gds` with no qualifying agent resolution yet
- new comment after the most recent agent resolution point
- comment explicitly asking for clarification, correction, or follow-up

### Visibility vs authority

Use a hybrid model:

- **Gitea labels/comments** are human-visible status markers
- **external scheduler task table** is the source of truth

Do not use "has the agent replied?" as the only completion signal.

## Task State Machine

The authoritative state machine lives in scheduler storage.

### States

- `detected`
- `queued`
- `claimed`
- `running`
- `reported`
- `completed`
- `needs_human`
- `expired`

### Semantics

- `detected`: raw event observed, not yet normalized
- `queued`: ready for a local client to claim
- `claimed`: reserved by a local client with a lease
- `running`: local agent actively processing
- `reported`: local result uploaded, scheduler finalization in progress
- `completed`: scheduler posted final reply and updated visible status
- `needs_human`: agent could not safely complete without clarification or manual intervention
- `expired`: lease timed out with no valid heartbeat and task is no longer actively owned

### Long-running tasks

Long execution is expected, not exceptional.

Required mechanisms:

- lease with expiration
- heartbeat renewal
- phase reporting
- stale-task recovery
- optional progress comment threshold

The system must never assume that lack of an immediate reply means failure.

## Lease, Heartbeat, and Progress Model

### Lease

When a local client claims a task, the scheduler grants a lease, for example 30 minutes.

Only the holder of a valid lease may report completion.

### Heartbeat

The local bridge renews the lease periodically, for example every 60 to 120 seconds.

Heartbeat payload includes:

- `task_id`
- `session_id`
- `phase`
- optional progress message

### Suggested phases

- `context_prepared`
- `editing`
- `verifying`
- `awaiting_human`
- `reporting`

### Progress comments

Default policy:

- do not post progress comments for short tasks
- if the task remains unfinished after a threshold, for example 10 minutes, scheduler posts one progress comment using the agent user
- do not spam periodic comments; only update on meaningful state changes

Every task must reach a terminal outcome:

- `completed`
- `needs_human`

No task should remain permanently in `running`.

## Gitea-visible Status Markers

Use lightweight labels only in the MVP.

Suggested labels:

- `agent/queued`
- `agent/running`
- `agent/done`
- `agent/human-needed`

These labels are for human visibility only. They must not replace the scheduler task table.

## Scheduler API

Expose a narrow HTTP/JSON interface from the scheduler.

### `POST /events/gitea`

Webhook entrypoint for Gitea events.

### `POST /poll/reconcile`

Manual or scheduled reconciliation endpoint for fallback polling.

### `POST /tasks/claim`

Atomically claims one task for a repository.

Example request:

```json
{
  "repo_key": "gitea://localhost/RuihuanFang/phononic-superconductor",
  "agent_user": "gds-agent",
  "worker_host": "fangr-laptop",
  "session_id": "local-codex-20260505-01"
}
```

### `POST /tasks/heartbeat`

Renews lease and updates phase.

Example request:

```json
{
  "task_id": "task_123",
  "session_id": "local-codex-20260505-01",
  "phase": "verifying",
  "message": "running snakemake"
}
```

### `POST /tasks/report`

Accepts the final result package from the local bridge.

### `POST /tasks/release`

Releases or abandons a claimed task explicitly.

## Standard Task Package

The scheduler packages issue/comment/provenance context so the local client does not need to reconstruct it from Gitea.

Example:

```json
{
  "task_id": "task_123",
  "repo": {
    "repo_key": "gitea://localhost/RuihuanFang/phononic-superconductor",
    "clone_url": "ssh://git@localhost:2222/RuihuanFang/phononic-superconductor.git",
    "default_branch": "main"
  },
  "event": {
    "type": "issue_comment",
    "issue_number": 17,
    "comment_id": 203,
    "comment_author": "alice",
    "comment_body": "please widen the output waveguide"
  },
  "issue": {
    "title": "MZI output mismatch",
    "body": "...",
    "labels": ["gds"]
  },
  "provenance": {
    "script": "designs/example_mzi.py",
    "function": "mzi",
    "line": 34,
    "cell": "straight",
    "layer": "WG"
  },
  "context": {
    "unreplied_reason": "new_comment_after_last_agent_reply",
    "last_agent_comment_id": 180
  }
}
```

## Result Package

The local bridge reports a structured terminal result instead of directly mutating Gitea.

### Completed example

```json
{
  "task_id": "task_123",
  "session_id": "local-codex-20260505-01",
  "status": "completed",
  "summary": "Adjusted output straight width and verified build.",
  "reply_body": "Automated fix applied:\n\n- **Change**: ...",
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

### Human-needed example

```json
{
  "task_id": "task_123",
  "session_id": "local-codex-20260505-01",
  "status": "needs_human",
  "summary": "Request is ambiguous.",
  "reply_body": "I need clarification on whether ...",
  "build": {
    "status": "not_run"
  }
}
```

## Local Bridge Model

The local bridge should exist in two forms:

- a thin CLI
- a Codex skill built on top of the CLI

### CLI responsibilities

- detect current repository identity from `git remote origin`
- call `claim`
- optionally persist the received task package to a temporary JSON file
- manage background heartbeat while work is running
- submit `report` or `release`

### Minimum CLI commands

- `agent-bridge claim`
- `agent-bridge heartbeat <task-id>`
- `agent-bridge report <task-id> --file result.json`
- `agent-bridge release <task-id> --reason "..."`

Enhanced commands:

- `agent-bridge inbox --global`
- `agent-bridge peek`
- `agent-bridge status <task-id>`

### Skill responsibilities

The skill should orchestrate the local workflow, not replace scheduler logic.

It should:

- claim a task for the current repository
- inject the task package into the active Codex session as structured context
- keep the heartbeat alive during long operations
- help assemble the final result package
- report results back through the CLI

## Default User Experience

### Default mode

From inside a repository:

- run the skill or CLI
- only tasks for that repository's `repo_key` are considered

### Enhanced mode

Outside a repository:

- inspect a global inbox
- choose a task
- switch into the appropriate local repository
- attach and process there

This matches the chosen rule:

- default is repository-scoped
- global inbox is an optional enhancement

## MVP Scope

The first version should include:

- one `agent-scheduler` container
- webhook + polling fallback
- task table with the chosen state machine
- claim/heartbeat/report/release API
- lightweight Gitea labels
- local `agent-bridge` CLI
- local Codex skill built on the CLI

The MVP should explicitly avoid:

- embedding agent inference in remote containers
- modifying Gitea core to host the task state machine
- complex multi-tenant permissions
- sophisticated queue prioritization
- GUI clients
- always-on local daemon requirements
- full ephemeral worker deployment before it is justified

## Deployment Recommendation

### MVP deployment

- `gitea`
- `agent-scheduler`
- local `agent-bridge`

The worker remains a logical boundary implemented inside scheduler for now.

### Later evolution

Split the worker into a real ephemeral container only if:

- repository-specific preprocessing becomes expensive
- security isolation needs increase
- multiple execution backends need different preprocessing stages

## Risks

### 1. Mis-detection of "unhandled" tasks

Mitigation:

- use hybrid visible marker + authoritative task table
- maintain stable dedupe keys for both issues and comments

### 2. Long-running task orphaning

Mitigation:

- lease
- heartbeat
- timeout recovery
- terminal-state enforcement

### 3. Local CLI/skill drift

Mitigation:

- keep scheduler protocol narrow
- let skill wrap the CLI instead of reimplementing the protocol

### 4. Early over-containerization

Mitigation:

- keep worker logical, not physical, in the MVP

## Open Questions

- exact threshold for progress comments
- storage backend for scheduler task table
- authentication model for local bridge to scheduler
- whether repository-level configuration should live in the repository or in scheduler
- how aggressively comment events should auto-create follow-up tasks

## Recommendation

Proceed with the MVP as:

- independent `agent-scheduler`
- no Gitea core ownership of task orchestration
- local repository-first bridge workflow
- CLI + skill on the local side
- long-running task support through lease and heartbeat

This is the smallest design that preserves maintainability, keeps the real agent execution local, and cleanly separates Gitea integration from agent workflow orchestration.
