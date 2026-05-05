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
    """Run a design script with the forked gdsfactory.

    If a Snakefile exists in the workspace, use snakemake for a proper
    pipeline build (which produces all GDS files with provenance).
    Otherwise fall back to running the script directly.
    """
    env = os.environ.copy()
    env["GDS_PROJECT_ROOT"] = str(workspace)
    env["PYTHONPATH"] = str(workspace) + ":" + env.get("PYTHONPATH", "")

    snakefile = workspace / "Snakefile"
    if snakefile.exists():
        design_name = pathlib.Path(design_path).stem
        # Delete stale GDS for this design so snakemake rebuilds it
        gds_path = workspace / "gds" / f"{design_name}.gds"
        gds_path.unlink(missing_ok=True)
        return subprocess.run(
            [
                "snakemake", "build_gds",
                "--snakefile", str(snakefile),
                "--config", f"design={design_name}",
                "--cores", "4",
                "--printshellcmds",
            ],
            cwd=str(workspace),
            capture_output=True, text=True,
            timeout=TIMEOUT,
            env=env,
        )

    # No Snakefile — run the script directly via runpy for provenance
    script_path = str(workspace / design_path)
    wrapper = (
        "import runpy, gdsfactory as gf; "
        "gf.gpdk.PDK.activate(); "
        f"runpy.run_path({script_path!r}, run_name='__main__')"
    )
    return subprocess.run(
        ["python", "-c", wrapper],
        cwd=str(workspace),
        capture_output=True, text=True,
        timeout=TIMEOUT,
        env=env,
    )


def _snapshot_gds(workspace: pathlib.Path) -> dict[str, float]:
    """Return {relative_path: mtime} for all .gds files in workspace."""
    snap = {}
    for gds in workspace.rglob("*.gds"):
        rel = str(gds.relative_to(workspace))
        snap[rel] = gds.stat().st_mtime
    return snap


def _collect_and_cache(
    workspace: pathlib.Path,
    owner: str,
    repo: str,
    ref: str,
    before: dict[str, float],
) -> list[str]:
    """Copy NEW or MODIFIED .gds files to build cache. *before* is a pre-build
    snapshot from ``_snapshot_gds()``; files whose path+mtime match are skipped
    (they were extracted from git and are stale).
    """
    cache_dir = BUILD_CACHE / owner.lower() / repo.lower() / ref
    cached = []
    for gds in workspace.rglob("*.gds"):
        rel = str(gds.relative_to(workspace))
        # Skip files that already existed with same mtime (pre-built, from git)
        if rel in before and gds.stat().st_mtime == before[rel]:
            continue
        dest = cache_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gds, dest)
        cached.append(rel)
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

        gds_before = _snapshot_gds(ws)
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

        cached = _collect_and_cache(ws, owner, repo, ref, gds_before)
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
    """Run the full build pipeline (snakemake if available, else all designs)."""
    owner, name = repo.split("/")
    bare = REPOS_DIR / owner.lower() / f"{name.lower()}.git"
    if not bare.exists():
        raise HTTPException(404, f"Repo not found: {repo}")

    ws = pathlib.Path(tempfile.mkdtemp(prefix="gdsbuild-all-"))
    try:
        if not _extract_repo(bare, ref, ws):
            raise HTTPException(500, "Failed to extract repo")

        gds_before = _snapshot_gds(ws)

        snakefile = ws / "Snakefile"
        if snakefile.exists():
            # Remove stale pre-existing GDS files so snakemake rebuilds them
            for rel, _mtime in gds_before.items():
                (ws / rel).unlink(missing_ok=True)

            # Run snakemake full pipeline (rule 'all')
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
            cached = _collect_and_cache(ws, owner, name, ref, gds_before)
            return {
                "status": "ok" if result.returncode == 0 else "build_failed",
                "method": "snakemake",
                "returncode": result.returncode,
                "stdout": result.stdout[-3000:] if result.stdout else "",
                "stderr": result.stderr[-3000:] if result.stderr else "",
                "built_files": cached,
            }

        # No Snakefile — discover and build individual designs
        designs = _find_py_files(ws, "designs")
        results = []
        for d in designs:
            try:
                r = do_build(owner, name, d, ref)
                results.append(r)
            except Exception as e:
                results.append({"status": "error", "design": d, "error": str(e)})
        return {"status": "ok", "method": "individual", "results": results}

    finally:
        shutil.rmtree(ws, ignore_errors=True)
