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
