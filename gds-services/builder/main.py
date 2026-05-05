"""GDS Builder — builds .gds files from designs using forked gdsfactory."""
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Query, Request

app = FastAPI(title="gds-builder")
REPOS_DIR = pathlib.Path("/data/git/repositories")
BUILD_CACHE = pathlib.Path("/data/build-cache")
TIMEOUT = 600  # 10 min per build
MANIFEST_FILE = "manifest.json"


def _extract_repo(bare_repo: pathlib.Path, ref: str, workspace: pathlib.Path) -> bool:
    """Extract repo contents at *ref* into *workspace* using git archive."""
    result = subprocess.run(
        ["git", "--git-dir", str(bare_repo), "archive", ref],
        capture_output=True,
    )
    if result.returncode != 0:
        return False
    result2 = subprocess.run(
        ["tar", "-x", "-C", str(workspace)],
        input=result.stdout,
        capture_output=True,
    )
    return result2.returncode == 0


def _find_py_files(workspace: pathlib.Path, subdir: str = "designs") -> list[str]:
    """Find .py files under *subdir* in the workspace."""
    d = workspace / subdir
    if not d.exists():
        return []
    return [str(p.relative_to(workspace)) for p in d.rglob("*.py")]


# ── Manifest ──────────────────────────────────────────────────────────────────

def _source_hash(workspace: pathlib.Path, design_name: str) -> str:
    """SHA256 of design file + Snakefile + build scripts."""
    h = hashlib.sha256()
    for rel in [
        f"designs/{design_name}.py",
        "Snakefile",
        "scripts/build_gds.py",
        "scripts/validate.py",
    ]:
        fp = workspace / rel
        if fp.exists():
            h.update(fp.read_bytes())
    return h.hexdigest()


def _load_manifest(cache_dir: pathlib.Path) -> dict:
    mf = cache_dir / MANIFEST_FILE
    if mf.exists():
        return json.loads(mf.read_text())
    return {}


def _save_manifest(cache_dir: pathlib.Path, manifest: dict, ref: str):
    cache_dir.mkdir(parents=True, exist_ok=True)
    manifest["ref"] = ref
    manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
    (cache_dir / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2))


def _is_stale(workspace: pathlib.Path, design_name: str,
              cache_dir: pathlib.Path, manifest: dict) -> bool:
    """True if *design_name* needs rebuilding (hash changed or files missing)."""
    current_hash = _source_hash(workspace, design_name)
    entry = manifest.get("designs", {}).get(design_name)
    if not entry:
        return True
    if entry.get("source_hash") != current_hash:
        return True
    for gf in entry.get("gds_files", []):
        if not (cache_dir / gf).exists():
            return True
    return False


def _update_manifest(manifest: dict, design_name: str,
                     source_hash: str, gds_files: list[str]):
    manifest.setdefault("designs", {})[design_name] = {
        "source_hash": source_hash,
        "gds_files": gds_files,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
    }


# ── Build ─────────────────────────────────────────────────────────────────────

def _run_build(design_path: str, workspace: pathlib.Path) -> subprocess.CompletedProcess:
    """Run a design script with the forked gdsfactory.

    If a Snakefile exists, use snakemake. Otherwise run the script directly.
    """
    env = os.environ.copy()
    env["GDS_PROJECT_ROOT"] = str(workspace)
    env["PYTHONPATH"] = str(workspace) + ":" + env.get("PYTHONPATH", "")

    snakefile = workspace / "Snakefile"
    if not snakefile.exists():
        raise FileNotFoundError("No Snakefile in repo — only snakemake builds are supported")

    design_name = pathlib.Path(design_path).stem
    return subprocess.run(
        [
            "snakemake", f"gds/{design_name}.gds",
            "--snakefile", str(snakefile),
            "--cores", "4",
            "--printshellcmds",
        ],
        cwd=str(workspace),
        capture_output=True, text=True,
        timeout=TIMEOUT,
        env=env,
    )


def _collect_and_cache(
    workspace: pathlib.Path,
    owner: str,
    repo: str,
    ref: str,
) -> list[str]:
    """Copy all .gds files from workspace to build cache."""
    cache_dir = BUILD_CACHE / owner.lower() / repo.lower() / ref
    cached = []
    for gds in workspace.rglob("*.gds"):
        rel = str(gds.relative_to(workspace))
        dest = cache_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gds, dest)
        cached.append(rel)
    return cached


def do_build(owner: str, repo: str, design: str, ref: str = "main") -> dict:
    """Core build logic. Returns result dict with status, built_files, etc."""
    bare = REPOS_DIR / owner.lower() / f"{repo.lower()}.git"
    if not bare.exists():
        raise HTTPException(404, f"Repo not found: {owner}/{repo}")

    ws = pathlib.Path(tempfile.mkdtemp(prefix="gdsbuild-"))
    try:
        if not _extract_repo(bare, ref, ws):
            raise HTTPException(500, "Failed to extract repo from git archive")

        if not (ws / design).exists():
            raise HTTPException(404, f"Design file not found: {design}")

        design_name = pathlib.Path(design).stem
        result = _run_build(design, ws)

        stdout_tail = result.stdout[-3000:] if result.stdout else ""
        stderr_tail = result.stderr[-3000:] if result.stderr else ""

        if result.returncode != 0:
            return {
                "status": "build_failed",
                "design": design,
                "ref": ref,
                "returncode": result.returncode,
                "stdout": stdout_tail,
                "stderr": stderr_tail,
                "built_files": [],
            }

        cached = _collect_and_cache(ws, owner, repo, ref)

        # Update manifest
        cache_dir = BUILD_CACHE / owner.lower() / repo.lower() / ref
        manifest = _load_manifest(cache_dir)
        h = _source_hash(ws, design_name)
        _update_manifest(manifest, design_name, h, cached)
        _save_manifest(cache_dir, manifest, ref)

        return {
            "status": "ok",
            "design": design,
            "ref": ref,
            "stdout": stdout_tail,
            "stderr": stderr_tail,
            "rel_files": cached,
        }
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "design": design,
            "ref": ref,
            "stderr": f"Build timed out after {TIMEOUT}s",
        }
    finally:
        shutil.rmtree(ws, ignore_errors=True)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/build")
def build_design(
    repo: str = Query(...),
    design: str = Query(...),
    ref: str = Query("main"),
):
    """Build a single design unconditionally."""
    owner, name = repo.split("/")
    try:
        result = do_build(owner, name, design, ref)
        if result["status"] == "build_failed":
            raise HTTPException(422, detail=result)
        if result["status"] == "timeout":
            raise HTTPException(408, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Build error: {e}")


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
            shutil.rmtree(ws, ignore_errors=True)
            return {"status": "fresh", "design": design}

        result = do_build(owner, name, design, ref)
        return result
    except Exception:
        shutil.rmtree(ws, ignore_errors=True)
        raise


@app.post("/build/all")
def build_all(
    repo: str = Query(...),
    ref: str = Query("main"),
):
    """Run the full build pipeline (snakemake if available, else all designs)."""
    owner, name = repo.split("/")
    bare = REPOS_DIR / owner.lower() / f"{name.lower()}.git"
    if not bare.exists():
        raise HTTPException(404, f"Repo not found: {repo}")

    ws = pathlib.Path(tempfile.mkdtemp(prefix="gdsbuild-all-"))
    try:
        if not _extract_repo(bare, ref, ws):
            raise HTTPException(500, "Failed to extract repo")

        cache_dir = BUILD_CACHE / owner.lower() / name.lower() / ref
        manifest = _load_manifest(cache_dir)

        snakefile = ws / "Snakefile"
        if snakefile.exists():
            env = os.environ.copy()
            env["GDS_PROJECT_ROOT"] = str(ws)
            env["PYTHONPATH"] = str(ws) + ":" + env.get("PYTHONPATH", "")
            result = subprocess.run(
                [
                    "snakemake",
                    "--snakefile", str(snakefile),
                    "--cores", "4",
                    "--printshellcmds",
                ],
                cwd=str(ws),
                capture_output=True, text=True,
                timeout=TIMEOUT,
                env=env,
            )
            cached = _collect_and_cache(ws, owner, name, ref)

            # Update manifest for each design
            for d in _find_py_files(ws, "designs"):
                dn = pathlib.Path(d).stem
                design_gds = [c for c in cached if dn in c]
                h = _source_hash(ws, dn)
                _update_manifest(manifest, dn, h, design_gds)
            _save_manifest(cache_dir, manifest, ref)

            return {
                "status": "ok" if result.returncode == 0 else "build_failed",
                "method": "snakemake",
                "returncode": result.returncode,
                "stdout": result.stdout[-3000:] if result.stdout else "",
                "stderr": result.stderr[-3000:] if result.stderr else "",
                "built_files": cached,
            }

        # No Snakefile — not supported
        raise HTTPException(400, "No Snakefile found in repo. Only snakemake builds are supported.")

    finally:
        shutil.rmtree(ws, ignore_errors=True)


@app.post("/webhook")
async def webhook(request: Request):
    """Handle Gitea push webhook. Rebuild affected designs."""
    body = await request.json()

    repo_full = body.get("repository", {}).get("full_name", "")
    ref = body.get("ref", "").replace("refs/heads/", "")
    commits = body.get("commits", [])

    if not repo_full or not ref:
        return {"status": "ignored", "reason": "missing repo or ref"}

    owner, name = repo_full.split("/")
    bare = REPOS_DIR / owner.lower() / f"{name.lower()}.git"
    if not bare.exists():
        return {"status": "ignored", "reason": "repo not found"}

    # Collect changed .py files from all commits
    changed_files = set()
    for c in commits:
        for fn in c.get("added", []) + c.get("modified", []):
            if fn.endswith(".py") or fn == "Snakefile":
                changed_files.add(fn)

    # Determine which designs are affected
    designs_to_check = set()
    infrastructure_changed = False
    for cf in changed_files:
        if cf == "Snakefile" or cf.startswith("scripts/"):
            infrastructure_changed = True
        if cf.startswith("designs/") and cf.endswith(".py"):
            designs_to_check.add(pathlib.Path(cf).stem)

    if infrastructure_changed:
        # Rebuild everything
        try:
            r = build_all(repo=repo_full, ref=ref)
            return {"status": "ok", "trigger": "infrastructure_change", "result": r}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    if not designs_to_check:
        return {"status": "ok", "message": "no design changes detected"}

    # Check and rebuild each affected design
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


@app.get("/manifest")
def get_manifest(
    repo: str = Query(...),
    ref: str = Query("main"),
):
    """Return the build manifest for inspection."""
    owner, name = repo.split("/")
    cache_dir = BUILD_CACHE / owner.lower() / name.lower() / ref
    return _load_manifest(cache_dir)
