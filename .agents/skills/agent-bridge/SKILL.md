---
name: agent-bridge
description: Claim a pending repository-scoped agent task from the remote scheduler, work it locally in the current repository, and report the result back.
---

# Agent Bridge

Use this skill when you are inside a checked-out repository and want to process a remote Gitea issue/comment task through the local scheduler bridge workflow.

## Workflow

1. Confirm the current directory is the intended repository.
2. Run `python -m tools.agent_bridge claim`.
3. Read the returned task package and use it as the active task context.
4. If the task will run for a while, start a heartbeat loop through `tools.agent_bridge.heartbeat`.
5. Perform the repository changes, validation, commit, and PR flow locally.
6. Write a result JSON file with:
   - `status`
   - `summary`
   - `reply_body`
   - `git`
   - `build`
   - `artifacts`
7. Run `python -m tools.agent_bridge report <task_id> --session-id <session_id> --file <result.json>`.
8. If the task cannot proceed safely, run `python -m tools.agent_bridge release <task_id> --session-id <session_id> --reason "<reason>"`.

## Notes

- The scheduler decides ownership and status. Do not mutate remote issue state directly from this skill.
- Default behavior is repository-scoped: it only claims tasks matching the current repo's `git remote origin`.
- The scheduler is responsible for the final issue/comment reply and visible labels.
