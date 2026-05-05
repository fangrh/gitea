"""GDS Builder — builds .gds files from designs using forked gdsfactory."""
import os
import pathlib
import shutil
import subprocess
import tempfile
from fastapi import FastAPI, HTTPException, Query

app = FastAPI(title="gds-builder")
REPOS_DIR = pathlib.Path("/data/git/repositories")
BUILD_CACHE = pathlib.Path("/data/build-cache")
TIMEOUT = 600  # 10 min per build


def _extract_repo(bare_repo: pathlib.Path, ref: str, workspace: pathlib.Path) -> bool:
    """Extract repo contents at *ref* into *workspace* using git archive."""
    result = subprocess.run(
        ["git", "--git-dir", str(bare_repo), "archive", ref],
        capture_output=True,
    )
    if result.returncode != 0:
        return False
    # git archive outputs a tar stream
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


def _run_build(design_path: str, workspace: pathlib.Path) -> subprocess.CompletedProcess:
    """Run a design script with the forked gdsfactory."""
    env = os.environ.copy()
    env["GDS_PROJECT_ROOT"] = str(workspace)
    env["PYTHONPATH"] = str(workspace) + ":" + env.get("PYTHONPATH", "")
    return subprocess.run(
        ["python", str(workspace / design_path)],
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
    """Copy .gds files from workspace to build cache. Return relative paths."""
    cache_dir = BUILD_CACHE / owner.lower() / repo.lower() / ref
    gds_files = list(workspace.rglob("*.gds"))
    cached = []
    for gds in gds_files:
        # Preserve relative path structure from workspace
        rel = gds.relative_to(workspace)
        dest = cache_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gds, dest)
        cached.append(str(rel))
    return cached


def do_build(owner: str, repo: str, design: str, ref: str = "main") -> dict:
    """Core build logic, callable internally and from endpoints."""
    bare = REPOS_DIR / owner.lower() / f"{repo.lower()}.git"
    if not bare.exists():
        raise HTTPException(404, f"Repo not found: {owner}/{repo}")

    ws = pathlib.Path(tempfile.mkdtemp(prefix="gdsbuild-"))
    try:
        if not _extract_repo(bare, ref, ws):
            raise HTTPException(500, "Failed to extract repo from git archive")

        if not (ws / design).exists():
            raise HTTPException(404, f"Design file not found in repo: {design}")

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
        return {
            "status": "ok",
            "design": design,
            "ref": ref,
            "stdout": stdout_tail,
            "stderr": stderr_tail,
            "built_files": [str(BUILD_CACHE / owner.lower() / repo.lower() / ref / c) for c in cached],
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/build")
def build_design(
    repo: str = Query(...),
    design: str = Query(...),
    ref: str = Query("main"),
):
    """Build a single design file into GDS."""
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


@app.post("/build/all")
def build_all(
    repo: str = Query(...),
    ref: str = Query("main"),
):
    """Discover and build all design files in a repo."""
    owner, name = repo.split("/")
    bare = REPOS_DIR / owner.lower() / f"{name.lower()}.git"
    if not bare.exists():
        raise HTTPException(404, f"Repo not found: {repo}")

    # Use a temporary workspace just to discover design files
    ws = pathlib.Path(tempfile.mkdtemp(prefix="gdsbuild-discover-"))
    try:
        if not _extract_repo(bare, ref, ws):
            raise HTTPException(500, "Failed to extract repo")

        designs = _find_py_files(ws, "designs")
    finally:
        shutil.rmtree(ws, ignore_errors=True)

    if not designs:
        return {"status": "ok", "message": "No design files found in designs/", "results": []}

    results = []
    for d in designs:
        try:
            r = do_build(owner, name, d, ref)
            results.append(r)
        except Exception as e:
            results.append({"status": "error", "design": d, "error": str(e)})

    return {"status": "ok", "built": len(results), "results": results}
