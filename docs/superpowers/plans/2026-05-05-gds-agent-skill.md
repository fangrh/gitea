# GDS Agent Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a single Claude Code skill `/gds-agent` that polls Gitea for open issues labeled 'gds', processes them (modify code, build, push, PR, reply), and tracks state locally — no scheduler service needed.

**Architecture:** A project-level skill file (`.claude/skills/gds-agent.md`) that Claude Code loads on `/gds-agent`. The skill instructs Claude to call the Gitea REST API via `curl`, parse JSON responses, edit Python design files, run snakemake, and execute git commands. State is tracked in `.gds-agent/state.json`.

**Tech Stack:** Claude Code skill (markdown), Gitea REST API v1, git CLI, snakemake, curl, jq (optional)

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `.claude/skills/gds-agent.md` | Create | Skill definition — instructions Claude follows when user runs `/gds-agent` |
| `.gds-agent/state.json` | Create at runtime | Tracks processed issue IDs (gitignored) |
| `.gitignore` (phononic-superconductor) | Modify | Add `.gds-agent/` entry |
| `AGENTS.md` | Modify | Update to reference `/gds-agent` skill instead of `agent.cli register` |
| `docker-compose.yml` | Modify | Remove `agent-scheduler` service |
| `agent-services/scheduler/` | Delete | Replaced by skill |

---

### Task 1: Create the GDS Agent Skill

**Files:**
- Create: `.claude/skills/gds-agent.md`

- [ ] **Step 1: Create `.claude/skills/` directory and skill file**

```markdown
---
name: gds-agent
description: Process open Gitea issues labeled 'gds' — read provenance, modify design code, build, push, open PR, and reply. Run this in a GDS design repo with git remote pointing to Gitea.
---

# GDS Agent — Issue Processor

You are a photonic design assistant. Process all new Gitea issues labeled 'gds'.

## Prerequisites Check

Before starting, verify these are available. If any fail, stop and report:

1. **Gitea token**: Read `$GITEA_TOKEN` env var. If empty, tell user:
   > Set GITEA_TOKEN before running: `export GITEA_TOKEN=your-token`
   > Get tokens at: Gitea → Settings → Applications → Generate Token

2. **Git remote**: Run `git remote get-url origin`. Parse it to extract:
   - Gitea base URL (e.g. `http://localhost:3000` or `https://gitea.example.com`)
   - Owner and repo name (e.g. `RuihuanFang/phononic-superconductor`)
   
   For SSH URLs like `git@host:owner/repo.git` → base URL is `http://host` (or `https://host`)
   For HTTP URLs like `http://host:3000/owner/repo.git` → base URL is `http://host:3000`
   
   If `.gds-agent.yml` exists in the repo root, use its `gitea_url`, `repo`, and `token_env` values to override.

3. **Verify API access**: Run `curl -s -H "Authorization: token $GITEA_TOKEN" {gitea_url}/api/v1/repos/{owner}/{repo}` and check for a valid JSON response with `"id"` field.

## Fetch Issues

Run:
```bash
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "{gitea_url}/api/v1/repos/{owner}/{repo}/issues?labels=gds&state=open&type=issue" 
```

Parse the JSON array. Each issue has `number`, `title`, `body`.

## Filter Already Processed

Read `.gds-agent/state.json`. If it doesn't exist, create it:
```bash
mkdir -p .gds-agent && echo '{"processed":[]}' > .gds-agent/state.json
```

Skip any issue whose `number` is in the `processed` array.

If no new issues remain, report "No new issues to process" and stop.

## Process Each Issue

Sort new issues by number (ascending). For each:

### 1. Parse Provenance

Extract JSON from the issue body between `<!-- GDS-PROVENANCE` and `GDS-PROVENANCE -->` markers.

If no provenance found, post a comment:
```bash
curl -s -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body":"Unable to process this issue: no provenance metadata found.\n\nPlease use the GDS Viewer to create issues — it embeds provenance automatically."}' \
  "{gitea_url}/api/v1/repos/{owner}/{repo}/issues/{number}/comments"
```
Add issue number to processed list and skip.

### 2. Validate

- `provenance.script` must start with `designs/` and end with `.py`
- The file must exist locally (`ls {provenance.script}`)
- `provenance.script` must not be in `scripts/` or `Snakefile`

If validation fails, post a comment explaining why and skip.

### 3. Read and Modify Code

Read the source file at `provenance.script`. Apply the change described in the issue body (the plain text after the `GDS-PROVENANCE -->` marker).

Follow these rules:
- Only modify the file specified in provenance
- Preserve the function signature unless the issue explicitly asks to change parameters
- Keep imports minimal — use gdsfactory components already in the file
- Do not delete existing components — only modify or extend

### 4. Verify Build

Run:
```bash
snakemake --cores 4
```

If the build fails:
```bash
# Post error comment
curl -s -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"body\":\"Build failed after applying changes. Error:\\n\\n<last 20 lines of snakemake output>\\n\\nNot pushing. Please review and update the issue.\"}" \
  "{gitea_url}/api/v1/repos/{owner}/{repo}/issues/{number}/comments"
```
Add to processed list. Skip git operations for this issue.

### 5. Git Operations

Generate a short description slug from the issue title (lowercase, hyphens, max 40 chars).

```bash
git checkout main
git pull origin main
git checkout -b fix/{issue_number}-{slug}
git add {provenance.script}
git commit -m "fix(design): {short description}

Closes #{issue_number}"
git push -u origin fix/{issue_number}-{slug}
```

### 6. Create Pull Request

```bash
curl -s -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"fix(design): {short description}\",\"body\":\"Automated fix for #{issue_number}\\n\\n**Change**: {what was modified}\\n**File**: {provenance.script}\\n\\nCloses #{issue_number}\",\"head\":\"fix/{issue_number}-{slug}\",\"base\":\"main\"}" \
  "{gitea_url}/api/v1/repos/{owner}/{repo}/pulls"
```

Capture the PR URL from the response (`html_url` field).

### 7. Reply to Issue

```bash
curl -s -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"body\":\"Automated fix applied:\\n\\n- **Change**: {what was modified}\\n- **File**: {provenance.script}\\n- **PR**: {pr_url}\\n- **Build**: passed\\n\\nPlease review the PR and merge if satisfactory.\"}" \
  "{gitea_url}/api/v1/repos/{owner}/{repo}/issues/{number}/comments"
```

## Update State

After processing all issues, write updated state:
```bash
echo '{"processed":[12,15,18]}' > .gds-agent/state.json
```

## Report

Print a summary:
```
Processed N issues:
  #12 fix(design): widen MZI arm gap — PR #5 (passed)
  #13 fix(design): add waveguide taper — build failed, see comment
```

## Safety Rules
- Never push to `main` directly
- Never modify `scripts/` or `Snakefile` unless the issue explicitly requests it
- If snakemake fails, reply to the issue explaining the error instead of force-pushing
- If the request is ambiguous, reply asking for clarification rather than guessing
```

- [ ] **Step 2: Commit the skill file**

```bash
git add .claude/skills/gds-agent.md
git commit -m "feat: add /gds-agent skill for processing Gitea issues"
```

---

### Task 2: Update .gitignore and AGENTS.md

**Files:**
- Modify: `AGENTS.md`
- Reference: phononic-superconductor repo's `.gitignore` (add `.gds-agent/`)

- [ ] **Step 1: Update AGENTS.md to reference the skill**

Replace the current AGENTS.md content with:

```markdown
# AGENT.md — AI Agent Instructions

## Quick Start

Run the `/gds-agent` skill to process all new Gitea issues:

```
/gds-agent
```

This skill will:
1. Poll Gitea for open issues labeled 'gds'
2. Parse provenance from issue body (HTML comments)
3. Read the referenced source file
4. Make the requested change
5. Run: snakemake --cores 4  (verify build passes)
6. Git commit + push on a fix branch
7. Open a pull request
8. Reply to the issue with a summary

## Prerequisites

Set your Gitea API token:
```bash
export GITEA_TOKEN=your-token
```

Get tokens at: Settings → Applications → Generate Token.

## Issue Format
Issues contain provenance in HTML comments:
```html
<!-- GDS-PROVENANCE
{
  "script": "designs/ring.py",
  "function": "ring_resonator",
  "line": 12,
  "cell": "ring",
  "layer": "WG",
  "coordinates": [100.0, 50.0]
}
GDS-PROVENANCE -->

User's request in plain text here.
```

## Modification Rules
1. **Only modify the file specified in provenance** — do not touch unrelated files
2. **Preserve the function signature** unless the issue explicitly asks to change parameters
3. **Keep imports minimal** — use gdsfactory components already in the file
4. **Run snakemake before committing** — if the build fails, fix your change or report back
5. **Do not delete existing components** — only modify or extend

## Commit Message Format
```
fix(design): <short description>

Closes #<issue_number>
```

## Git Branch Naming
```
fix/<issue_number>-<short-description>
```

## Safety
- Never push to `main` directly
- Never modify `scripts/` or `Snakefile` unless the issue explicitly requests it
- If snakemake fails, reply to the issue explaining the error instead of force-pushing
- If the request is ambiguous, reply asking for clarification rather than guessing
```

- [ ] **Step 2: Add `.gds-agent/` to phononic-superconductor's .gitignore**

This step must be done in the phononic-superconductor repo:

```bash
cd /d/gds_argo/phononic-superconductor
echo -e "\n# Agent state\n.gds-agent/" >> .gitignore
git add .gitignore
git commit -m "chore: gitignore .gds-agent/ state directory"
git push origin main
```

- [ ] **Step 3: Commit AGENTS.md update in gitea repo**

```bash
cd /d/gds_argo/Gdslab/gitea
git add AGENTS.md
git commit -m "docs: update AGENTS.md to reference /gds-agent skill"
```

---

### Task 3: Remove Scheduler Service

**Files:**
- Modify: `docker-compose.yml`
- Delete: `agent-services/scheduler/` directory

- [ ] **Step 1: Remove agent-scheduler from docker-compose.yml**

Remove this entire block from `docker-compose.yml`:

```yaml
  agent-scheduler:
    build:
      context: ./agent-services/scheduler
    restart: unless-stopped
    networks:
      - gitea
    ports:
      - "127.0.0.1:8002:8002"
    volumes:
      - gitea-data:/data
```

- [ ] **Step 2: Stop and remove the running scheduler container**

```bash
docker compose stop agent-scheduler
docker compose rm -f agent-scheduler
```

- [ ] **Step 3: Delete the scheduler source directory**

```bash
rm -rf agent-services/scheduler/
```

If `agent-services/` is now empty, remove it too:
```bash
rmdir agent-services/ 2>/dev/null || true
```

- [ ] **Step 4: Commit cleanup**

```bash
git add docker-compose.yml
git rm -r agent-services/scheduler/
git commit -m "refactor: remove scheduler service — replaced by /gds-agent skill"
```

---

### Task 4: End-to-End Verification

**Files:** None (testing only)

- [ ] **Step 1: Verify skill is discoverable**

Run in the gitea repo:
```bash
ls -la .claude/skills/gds-agent.md
```
Confirm the file exists and contains the skill frontmatter.

- [ ] **Step 2: Verify docker compose is valid without scheduler**

```bash
docker compose config --quiet
```
Should exit 0 with no errors.

- [ ] **Step 3: Verify phononic-superconductor gitignore updated**

```bash
cd /d/gds_argo/phononic-superconductor
grep -q "\.gds-agent/" .gitignore && echo "OK" || echo "MISSING"
```

- [ ] **Step 4: Verify scheduler container removed**

```bash
docker ps --filter "name=scheduler" --format "{{.Names}}"
```
Should return empty (no running scheduler container).

- [ ] **Step 5: Manual test — create a test issue on Gitea**

1. Open `http://localhost:3000/RuihuanFang/phononic-superconductor/issues`
2. Create a new issue with label `gds`:
   ```
   Title: test agent workflow
   
   Body:
   <!-- GDS-PROVENANCE
   {
     "script": "designs/example_mzi.py",
     "function": "mzi",
     "line": 8,
     "cell": "mzi",
     "layer": "WG",
     "coordinates": [100.0, 50.0]
   }
   GDS-PROVENANCE -->
   
   Change the default gap from 10.0 to 15.0
   ```
3. Run `/gds-agent` in Claude Code from the phononic-superconductor repo
4. Verify:
   - Issue is picked up
   - `designs/example_mzi.py` gap changed from 10.0 to 15.0
   - snakemake passes
   - Branch `fix/<n>-change-gap` pushed
   - PR created
   - Issue comment posted

- [ ] **Step 6: Commit final state**

```bash
git push origin main
```

---

## Self-Review

**Spec coverage check:**
- [x] Configuration (.gds-agent.yml, env vars) → Task 1 Step 1 (skill handles all config)
- [x] Fetch issues from Gitea API → Task 1 Step 1 (skill Fetch Issues section)
- [x] Filter by state.json → Task 1 Step 1 (skill Filter section)
- [x] Parse provenance → Task 1 Step 1 (skill Parse Provenance section)
- [x] Validate provenance.script → Task 1 Step 1 (skill Validate section)
- [x] Modify code → Task 1 Step 1 (skill Modify section)
- [x] Run snakemake → Task 1 Step 1 (skill Build section)
- [x] Git commit + push → Task 1 Step 1 (skill Git section)
- [x] Create PR → Task 1 Step 1 (skill PR section)
- [x] Reply to issue → Task 1 Step 1 (skill Reply section)
- [x] Update state.json → Task 1 Step 1 (skill State section)
- [x] Error handling (all scenarios) → Task 1 Step 1 (skill handles each error inline)
- [x] Remote machine support → Implicit: only needs git + curl + GITEA_TOKEN
- [x] Cleanup scheduler → Task 3

**Placeholder scan:** No TBD/TODO found. All steps have complete code/instructions.

**Type consistency:** Issue `number` is used consistently as integer. Branch naming uses `{issue_number}-{slug}` throughout.
