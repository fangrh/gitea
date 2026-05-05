# GDS Agent Skill — Design Spec

## Context

Photonic designers create Gitea issues to request layout changes. An AI agent (Claude Code) runs locally in the GDS design repo and processes these issues: reads provenance, modifies Python design scripts, runs snakemake, pushes a fix branch, opens a PR, and replies to the issue.

The current implementation uses a scheduler service as intermediary, but its Gitea client is entirely mocked. The scheduler adds complexity without value — a single skill that directly calls the Gitea API and runs git commands is simpler, more reliable, and works from any machine that has git push access to Gitea.

## Architecture

```
Local GDS repo (any machine)
├── .gds-agent/
│   └── state.json          ← processed issue IDs
├── .gds-agent.yml           ← config (Gitea URL, token env var)
├── designs/*.py
├── Snakefile
└── ...

User runs: /gds-agent
    │
    ├─ Read config (.gds-agent.yml or env vars)
    ├─ Gitea API: list open issues with label 'gds'
    ├─ Filter already-processed (state.json)
    ├─ For each new issue:
    │    ├─ Parse provenance from HTML comment
    │    ├─ Read + modify source file
    │    ├─ Run snakemake to verify
    │    ├─ git commit + push (fix/{n}-desc)
    │    ├─ Gitea API: create PR
    │    └─ Gitea API: comment reply
    ├─ Update state.json
    └─ Report summary
```

## Configuration

### `.gds-agent.yml` (repo-local, gitignored)

```yaml
gitea_url: https://gitea.example.com   # inferred from git remote if omitted
token_env: GITEA_TOKEN                  # env var holding API token
repo: owner/repo                        # inferred from git remote if omitted
```

All fields optional — defaults are inferred from `git remote get-url origin`.

### Environment variable

`GITEA_TOKEN` must be set to a valid Gitea API token with repo read/write permissions. The skill fails immediately if this is missing.

### `.gds-agent/state.json`

```json
{
  "processed": [12, 15, 18]
}
```

Simple list of issue numbers that have been processed. Gitignored.

## Skill: `/gds-agent`

### Step 1: Initialize

1. Parse `git remote get-url origin` to extract Gitea base URL and `owner/repo`
2. Override with `.gds-agent.yml` if present
3. Read `GITEA_TOKEN` from environment
4. Load `.gds-agent/state.json` (create empty if missing)

### Step 2: Fetch Issues

```
GET {gitea_url}/api/v1/repos/{owner}/{repo}/issues
    ?labels=gds&state=open
```

Filter out issue numbers present in `state.json`. If no new issues, report and exit.

### Step 3: Process Each Issue

For each new issue (sorted by number ascending):

#### 3a. Parse Provenance

Extract JSON from `<!-- GDS-PROVENANCE ... GDS-PROVENANCE -->` HTML comment in issue body. If missing, post a comment asking for provenance and skip.

#### 3b. Validate

- `provenance.script` must start with `designs/` and end with `.py`
- File must exist locally

#### 3c. Modify Code

Read `provenance.script`, apply the change described in the issue body (plain text after the HTML comment), following AGENTS.md rules (preserve function signature, minimal imports, no deleting existing components).

#### 3d. Verify Build

Run `snakemake --cores 4`. If it fails:
- Post comment with error log excerpt
- Skip push/PR
- Still record issue as processed in state.json

#### 3e. Git Operations

```
git checkout -b fix/{issue_number}-{short-desc}
git add <changed files>
git commit -m "fix(design): <short desc>\n\nCloses #{issue_number}"
git push -u origin fix/{issue_number}-{short-desc}
```

#### 3f. Create PR

```
POST {gitea_url}/api/v1/repos/{owner}/{repo}/pulls
{
  "title": "fix(design): <short desc>",
  "body": "Automated fix for #{issue_number}\n\n<change summary>",
  "head": "fix/{issue_number}-{short-desc}",
  "base": "main"
}
```

#### 3g. Reply to Issue

```
POST {gitea_url}/api/v1/repos/{owner}/{repo}/issues/{n}/comments
{
  "body": "Automated fix applied:\n- **Change**: <what>\n- **File**: <script>\n- **PR**: <url>\n- **Build**: passed/failed"
}
```

### Step 4: Update State

Append processed issue numbers to `.gds-agent/state.json`.

### Step 5: Report

Print summary to user:
```
Processed 2 issues:
  #12 fix(design): widen MZI arm gap — PR #5 (passed)
  #13 fix(design): add waveguide taper — build failed, see comment
```

## Error Handling

| Scenario | Behavior |
|----------|----------|
| GITEA_TOKEN missing | Fail immediately with setup instructions |
| git remote is not Gitea | Fail, suggest configuring `.gds-agent.yml` |
| Issue has no provenance | Comment on issue asking for provenance, skip |
| provenance.script outside designs/ | Comment on issue refusing, cite safety rule |
| snakemake fails | Comment with error log, skip push/PR |
| git push fails | Comment explaining failure, keep local branch |
| PR creation fails | Comment with commit info for manual PR |
| Issue already processed | Skip silently |

## Remote Machine Support

The only requirements for running on a different machine:
- git remote origin points to the Gitea server
- SSH key or HTTP credential configured for git push
- `GITEA_TOKEN` env var set
- snakemake + gdsfactory installed locally

No scheduler service, no exposed ports, no webhook receivers needed.

## Cleanup

After implementing the skill, remove:
- `agent-services/scheduler/` directory
- `agent/` directory (CLI tools replaced by skill)
- `docker-compose.yml` scheduler service entry
- `agent-scheduler` container from deployment
