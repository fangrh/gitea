"""GDS Builder — builds .gds files from designs using forked gdsfactory."""
import pathlib
from fastapi import FastAPI, HTTPException

app = FastAPI(title="gds-builder")
REPOS_DIR = pathlib.Path("/data/git/repositories")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/build")
def build_design(repo: str, design: str):
    """Build one design into a GDS file. Full pipeline in next iteration."""
    owner, name = repo.split("/")
    path = REPOS_DIR / owner.lower() / f"{name.lower()}.git"
    if not path.exists():
        raise HTTPException(404, f"Repo not found: {repo}")
    return {"status": "not_implemented", "message": "Builder stub — full pipeline next"}


@app.post("/build/all")
def build_all(repo: str):
    """Rebuild all designs in a repo."""
    return {"status": "not_implemented", "message": "Full build pipeline next iteration"}
