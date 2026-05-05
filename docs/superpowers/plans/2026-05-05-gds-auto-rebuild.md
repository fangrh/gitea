# GDS Auto-Rebuild — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Builder auto-detects missing or stale GDS files and rebuilds them. Git stops tracking GDS files entirely — the build server manages its own GDS versioning via cache manifest.

**Architecture:** Gitea webhook on push → builder diffs affected designs → checks manifest for staleness → snakemake rebuilds only what changed. Viewer polls until build complete on cache miss.

**Tech Stack:** Python FastAPI, snakemake CLI, JSON manifest, Gitea webhook API

---

## Design Overview

### Manifest (`/data/build-cache/<owner>/<repo>/<ref>/manifest.json`)

```json
{
  "ref": "main",
  "updated_at": "2026-05-05T16:00:00Z",
  "designs": {
    "example_mzi": {
      "source_hash": "a1b2c3d4e5f6...",
      "gds_files": ["gds/example_mzi.gds", "mzi_example.gds"],
      "built_at": "2026-05-05T16:00:00Z",
      "status": "ok"
    },
    "markers": {
      "source_hash": "f6e5d4c3b2a1...",
      "gds_files": ["gds/markers.gds", "markers.gds"],
      "built_at": "2026-05-05T16:00:01Z",
      "status": "ok"
    }
  }
}
```

### Staleness detection

For each design `d`:
1. Compute `sha256(designs/d.py + Snakefile + scripts/build_gds.py + scripts/validate.py)` — the design file + build infrastructure
2. Compare with `manifest.designs[d].source_hash`
3. If different → rebuild
4. If any `manifest.designs[d].gds_files` missing from cache → rebuild
5. If manifest entry missing → rebuild

### Webhook flow

```
Git push → Gitea webhook → POST gds-builder:8001/webhook
  → git diff old..new → list changed .py files
  → for each changed design: check staleness → rebuild if needed
  → update manifest
```

### Git stops tracking GDS

- Add `*.gds` and `gds/` and `build/` to `.gitignore` in user repos
- `git rm --cached` for already-committed GDS files
- Builder no longer needs `_snapshot_gds()` / stale-file deletion workarounds

---

### Task 1: Remove GDS from git tracking in phononic-superconductor

**Files:**
- Modify: `D:\gds_argo\phononic-superconductor\.gitignore`
- Bash: `git rm --cached`

- [ ] **Step 1: Add GDS patterns to .gitignore**

```gitignore
# GDS build outputs — managed by gds-builder, not git
*.gds
gds/
build/
```

- [ ] **Step 2: Untrack existing GDS files**

```bash
cd phononic-superconductor
git rm --cached gds/example_mzi.gds gds/markers.gds 2>/dev/null
git rm --cached build/ 2>/dev/null
git add .gitignore
git commit -m "chore: stop tracking GDS files — build server manages GDS outputs"
```

- [ ] **Step 3: Clean builder cache of old lingering files**

```bash
docker exec gitea-gds-builder-1 rm -rf /data/build-cache/ruihuanfang/phononic-superconductor
```

---

### Task 2: Add manifest system to gds-builder

**Files:**
- Modify: `gds-services/builder/main.py`

- [ ] **Step 1: Add manifest read/write helpers**

```python
import hashlib
import json
from datetime import datetime, timezone

MANIFEST_FILE = "manifest.json"

def _source_hash(workspace: pathlib.Path, design_name: str) -> str:
    """Compute SHA256 of design file + build infrastructure files."""
    h = hashlib.sha256()
    files_to_hash = [
        workspace / "designs" / f"{design_name}.py",
        workspace / "Snakefile",
        workspace / "scripts" / "build_gds.py",
        workspace / "scripts" / "validate.py",
    ]
    for fp in files_to_hash:
        if fp.exists():
            h.update(fp.read_bytes())
    return h.hexdigest()


def _load_manifest(cache_dir: pathlib.Path) -> dict:
    """Load or create manifest.json."""
    mf = cache_dir / MANIFEST_FILE
    if mf.exists():
        return json.loads(mf.read_text())
    return {"designs": {}}


def _save_manifest(cache_dir: pathlib.Path, manifest: dict, ref: str):
    """Write manifest.json to cache directory."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest["ref"] = ref
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    (cache_dir / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2))
```

- [ ] **Step 2: Add staleness check**

```python
def _is_stale(workspace: pathlib.Path, design_name: str,
              cache_dir: pathlib.Path, manifest: dict) -> bool:
    """Return True if *design_name* needs rebuilding."""
    current_hash = _source_hash(workspace, design_name)
    entry = manifest.get("designs", {}).get(design_name)
    if not entry:
        return True  # never built
    if entry.get("source_hash") != current_hash:
        return True  # source changed
    # Check all expected GDS files exist in cache
    for gf in entry.get("gds_files", []):
        if not (cache_dir / gf).exists():
            return True  # file missing
    return False
```

- [ ] **Step 3: Update manifest after build**

```python
def _update_manifest(manifest: dict, design_name: str,
                     source_hash: str, gds_files: list[str]):
    manifest.setdefault("designs", {})[design_name] = {
        "source_hash": source_hash,
        "gds_files": gds_files,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
    }
```

- [ ] **Step 4: Commit staged builder changes**

```bash
git add gds-services/builder/main.py
git commit -m "feat(gds-builder): manifest-based staleness detection"
```

---

### Task 3: Add webhook endpoint and auto-rebuild endpoint

**Files:**
- Modify: `gds-services/builder/main.py`

- [ ] **Step 1: Add `/build/if-needed` endpoint**

```python
@app.post("/build/if-needed")
def build_if_needed(
    repo: str = Query(...),
    design: str = Query(...),
    ref: str = Query("main"),
):
    """Build a design only if stale or missing from cache."""
    owner, name = repo.split("/")
    bare = REPOS_DIR / owner.lower() / f"{name.lower()}.git"
    if not bare.exists():
        raise HTTPException(404, f"Repo not found: {repo}")

    cache_dir = BUILD_CACHE / owner.lower() / name.lower() / ref
    manifest = _load_manifest(cache_dir)

    ws = pathlib.Path(tempfile.mkdtemp(prefix="gdsbuild-check-"))
    try:
        if not _extract_repo(bare, ref, ws):
            raise HTTPException(500, "Failed to extract repo")

        design_name = pathlib.Path(design).stem
        if not _is_stale(ws, design_name, cache_dir, manifest):
            return {"status": "fresh", "design": design}
        # Need rebuild — use existing do_build logic
        result = do_build(owner, name, design, ref)
        if result["status"] == "ok":
            h = _source_hash(ws, design_name)
            _update_manifest(manifest, design_name, h, result["rel_files"])
            _save_manifest(cache_dir, manifest, ref)
        return result
    finally:
        shutil.rmtree(ws, ignore_errors=True)
```

- [ ] **Step 2: Add `/webhook` endpoint for Gitea push events**

```python
@app.post("/webhook")
async def webhook(request: Request):
    """Handle Gitea push webhook. Rebuild affected designs."""
    import json as _json
    body = await request.json()

    # Gitea webhook payload
    repo_full = body.get("repository", {}).get("full_name", "")
    ref = body.get("ref", "").replace("refs/heads/", "")
    commits = body.get("commits", [])

    if not repo_full or not ref:
        return {"status": "ignored"}

    owner, name = repo_full.split("/")
    bare = REPOS_DIR / owner.lower() / f"{name.lower()}.git"
    if not bare.exists():
        return {"status": "ignored", "reason": "repo not found"}

    # Find changed .py files
    changed_files = set()
    for c in commits:
        for fn in c.get("added", []) + c.get("modified", []):
            if fn.endswith(".py") or fn == "Snakefile":
                changed_files.add(fn)

    # Find which designs are affected
    designs_to_check = set()
    for cf in changed_files:
        if cf.startswith("designs/") and cf.endswith(".py"):
            designs_to_check.add(pathlib.Path(cf).stem)
        # If Snakefile or build scripts changed, rebuild ALL designs
        if cf == "Snakefile" or cf.startswith("scripts/"):
            # Discover all designs
            ws = pathlib.Path(tempfile.mkdtemp(prefix="gdsbuild-webhook-"))
            try:
                _extract_repo(bare, ref, ws)
                for pyf in (ws / "designs").rglob("*.py"):
                    designs_to_check.add(pyf.stem)
            finally:
                shutil.rmtree(ws, ignore_errors=True)

    if not designs_to_check:
        return {"status": "no_designs_affected"}

    # Check each design for staleness and rebuild
    results = []
    for dn in designs_to_check:
        try:
            design_path = f"designs/{dn}.py"
            r = build_if_needed(repo=repo_full, design=design_path, ref=ref)
            results.append({"design": dn, **r})
        except Exception as e:
            results.append({"design": dn, "status": "error", "error": str(e)})

    return {
        "status": "ok",
        "repo": repo_full,
        "ref": ref,
        "changed_files": list(changed_files),
        "results": results,
    }
```

- [ ] **Step 3: Update `/build/all` to use manifest**

Inside `/build/all`, after snakemake succeeds for each design, update and save the manifest so all files are tracked.

- [ ] **Step 4: Commit**

```bash
git add gds-services/builder/main.py
git commit -m "feat(gds-builder): webhook endpoint, /build/if-needed with manifest staleness check"
```

---

### Task 4: Wire Gitea webhook to builder

**Files:**
- Bash: configure webhook via Gitea API or `docker exec`

- [ ] **Step 1: Add webhook in Gitea for the target repo**

```bash
# Using Gitea API to create a webhook (or manual via UI)
curl -X POST "http://localhost:3000/api/v1/repos/RuihuanFang/phononic-superconductor/hooks" \
  -H "Authorization: token <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "gitea",
    "config": {
      "url": "http://gds-builder:8001/webhook",
      "content_type": "json"
    },
    "events": ["push"],
    "active": true
  }'
```

- [ ] **Step 2: Commit webhook setup instructions**

```bash
git add docs/ && git commit -m "docs: webhook setup for auto-rebuild"
```

---

### Task 5: Viewer polls on cache miss

**Files:**
- Modify: `gds-services/parser/main.py`
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Parser `/data` returns "building" status on cache miss**

When a GDS file is missing from both cache and git, return a response indicating the file is being built rather than a plain 404. The viewer can poll.

```python
@app.get("/data")
def get_gds_data(repo: str, ref: str = "main", path: str = "", poll: bool = False):
    ...
    # Cache miss — optionally trigger a build
    if not cache_file.exists() and not (repo_dir.exists() and ...):
        if poll:
            # Trigger async rebuild
            ...
            return Response(
                content=json.dumps({"status": "building"}),
                media_type="application/json",
                status_code=202,
            )
        raise HTTPException(404, ...)
```

- [ ] **Step 2: Viewer handles "building" state with retry**

```javascript
function loadGDSWithRetry(filePath, maxRetries, delay) {
    maxRetries = maxRetries || 30;
    delay = delay || 2000;
    var attempts = 0;
    function tryLoad() {
        fetch('/data?repo=...&path=...&poll=1')
            .then(function(r) {
                if (r.status === 202) {
                    // Still building — retry
                    attempts++;
                    if (attempts < maxRetries) {
                        showBuildingStatus(attempts);
                        setTimeout(tryLoad, delay);
                    }
                    return null;
                }
                return r.json();
            })
            .then(function(geojson) {
                if (geojson) renderGDS(geojson);
            });
    }
    tryLoad();
}
```

- [ ] **Step 3: Commit**

```bash
git add gds-services/parser/
git commit -m "feat(gds-viewer): poll-on-build for cache-miss GDS files"
```

---

### Task 6: End-to-end verification

- [ ] **Step 1: Delete all build cache**

```bash
docker exec gitea-gds-builder-1 rm -rf /data/build-cache/ruihuanfang/phononic-superconductor
```

- [ ] **Step 2: Open viewer — should trigger build and show spinner**

Open `http://localhost:3000/RuihuanFang/phononic-superconductor/gds`  
Expected: spinner → GDS loads with provenance

- [ ] **Step 3: Modify a design file and push**

Change something in `designs/example_mzi.py`, commit and push.
Expected: webhook fires → builder rebuilds only `example_mzi` → viewer shows updated layout

- [ ] **Step 4: Verify no GDS files in git**

Expected: `git status` in phononic-superconductor shows no `.gds` files tracked

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "test: end-to-end auto-rebuild verification passed"
```

---

### Rebuild Cost Summary

| Component | Files changed | Rebuild time |
|-----------|-------------|-------------|
| Builder (manifest logic) | `main.py` | ~10s |
| Parser (polling) | `main.py`, `viewer.html` | ~10s |
| Gitea | `gds.tmpl` (no changes) | 0 |
