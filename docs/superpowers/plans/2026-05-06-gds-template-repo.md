# GDS Template Repo & Skill Repo — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create two new repos on Gitea — a shared skill repo (`gds-agent-skill`) and a GDS project template (`gds-template`) — then link the template as a submodule in the gitea project repo.

**Architecture:** `GdsLab/gds-agent-skill` holds the `/gds-agent` skill file for one-command install. `GdsLab/gds-template` is a clean project skeleton (from phononic-superconductor, minus agent/ CLI and specific designs) with CLAUDE.md pointing users to install the skill. The gitea project repo adds `gds-template` as a submodule.

**Tech Stack:** Git, Gitea REST API v1, curl, snakemake, gdsfactory

---

## File Structure

| File | Action | Responsibility | Repo |
|------|--------|---------------|------|
| `.claude/skills/gds-agent.md` | Create | Skill definition (copy from gitea repo) | gds-agent-skill |
| `README.md` | Create | Install instructions | gds-agent-skill |
| `CLAUDE.md` | Create | Project instructions + skill install link | gds-template |
| `.gitignore` | Create | Ignore generated/agent files | gds-template |
| `config.yaml` | Create | Workflow configuration | gds-template |
| `Snakefile` | Create | Build pipeline rules | gds-template |
| `envs/gds.yaml` | Create | Conda environment spec | gds-template |
| `requirements.txt` | Create | Python dependencies | gds-template |
| `designs/markers.py` | Create | Example alignment marker design | gds-template |
| `scripts/build_gds.py` | Create | Python → GDS compiler | gds-template |
| `scripts/validate.py` | Create | Layout validation | gds-template |
| `scripts/report.py` | Create | Preview generation | gds-template |
| `gds-template/` | Add submodule | Link template into gitea project | gitea |

---

### Task 1: Create gds-agent-skill Repo

**Files:**
- Create: `gds-agent-skill/.claude/skills/gds-agent.md`
- Create: `gds-agent-skill/README.md`

- [ ] **Step 1: Create the repo directory locally**

```bash
mkdir -p /d/gds_argo/gds-agent-skill/.claude/skills
cd /d/gds_argo/gds-agent-skill
git init
```

- [ ] **Step 2: Copy the skill file from gitea repo**

```bash
cp /d/gds_argo/Gdslab/gitea/.claude/skills/gds-agent.md /d/gds_argo/gds-agent-skill/.claude/skills/gds-agent.md
```

- [ ] **Step 3: Create README.md**

Create `/d/gds_argo/gds-agent-skill/README.md`:

```markdown
# GDS Agent Skill

AI-powered photonic design assistant for Claude Code.

## Install

In your GDS design repo:

```bash
mkdir -p .claude/skills
curl -o .claude/skills/gds-agent.md \
  "$GITEA_URL/GdsLab/gds-agent-skill/raw/branch/main/.claude/skills/gds-agent.md"
```

Replace `$GITEA_URL` with your Gitea server URL (e.g. `http://localhost:3000`).

## Usage

1. Set your Gitea API token:
   ```bash
   export GITEA_TOKEN=your-token
   ```
2. Run in Claude Code:
   ```
   /gds-agent
   ```

## How It Works

The skill polls Gitea for open issues labeled 'gds', parses provenance metadata from the issue body, modifies the referenced design script, runs snakemake to verify the build, pushes a fix branch, opens a PR, and replies to the issue.

## Requirements

- Claude Code installed
- Gitea API token with repo read/write access
- Git remote origin pointing to Gitea
- snakemake + gdsfactory installed locally
```

- [ ] **Step 4: Commit and push to Gitea**

First, create the repo `GdsLab/gds-agent-skill` on Gitea:

```bash
curl -s -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"gds-agent-skill","description":"Shared Claude Code skill for automated GDS issue processing","private":false,"auto_init":false}' \
  "http://localhost:3000/api/v1/orgs/GdsLab/repos"
```

If the `GdsLab` org doesn't exist, create under the user instead:

```bash
curl -s -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"gds-agent-skill","description":"Shared Claude Code skill for automated GDS issue processing","private":false,"auto_init":false}' \
  "http://localhost:3000/api/v1/user/repos"
```

Then push:

```bash
cd /d/gds_argo/gds-agent-skill
git add .
git commit -m "feat: add /gds-agent skill definition with install instructions"
git remote add origin ssh://git@localhost:2222/{owner}/gds-agent-skill.git
git push -u origin main
```

Where `{owner}` is `GdsLab` if the org exists, otherwise the username.

---

### Task 2: Create gds-template Repo

**Files:**
- Create: `gds-template/CLAUDE.md`
- Create: `gds-template/.gitignore`
- Create: `gds-template/config.yaml`
- Create: `gds-template/Snakefile`
- Create: `gds-template/envs/gds.yaml`
- Create: `gds-template/requirements.txt`
- Create: `gds-template/designs/markers.py`
- Create: `gds-template/scripts/build_gds.py`
- Create: `gds-template/scripts/validate.py`
- Create: `gds-template/scripts/report.py`

- [ ] **Step 1: Create the repo directory and subdirectories**

```bash
mkdir -p /d/gds_argo/gds-template/{designs,scripts,envs}
cd /d/gds_argo/gds-template
git init
```

- [ ] **Step 2: Create CLAUDE.md**

Create `/d/gds_argo/gds-template/CLAUDE.md`:

```markdown
@CLAUDE.md

# GDS Design Project

## Build

```bash
snakemake --cores 4
```

## AI Agent (/gds-agent)

To enable automated issue processing from GDS Viewer:

```bash
mkdir -p .claude/skills
curl -o .claude/skills/gds-agent.md \
  "$GITEA_URL/GdsLab/gds-agent-skill/raw/branch/main/.claude/skills/gds-agent.md"
```

Replace `$GITEA_URL` with your Gitea server URL (e.g. `http://localhost:3000`).

Set your Gitea token: `export GITEA_TOKEN=your-token`

Run in Claude Code: `/gds-agent`

## Design Conventions

- Place design scripts in `designs/` (one component per file)
- Each script must define `main()`, `component`, or a callable returning a gdsfactory Component
- File name determines output GDS name: `designs/markers.py` → `gds/markers.gds`
- Run `snakemake --cores 4` before committing to verify builds pass
```

- [ ] **Step 3: Create .gitignore**

Create `/d/gds_argo/gds-template/.gitignore`:

```gitignore
# Generated outputs
gds/
reports/

# Python
__pycache__/
*.pyc
.venv/
env/

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Snakemake
.snakemake/

# Agent state
.gds-agent/
```

- [ ] **Step 4: Create config.yaml**

Create `/d/gds_argo/gds-template/config.yaml`:

```yaml
# GDS Design Workflow Configuration

designs_dir: designs
gds_dir: gds
report_dir: reports

# Build settings
threads: 4
```

- [ ] **Step 5: Create Snakefile**

Create `/d/gds_argo/gds-template/Snakefile`:

```python
"""
GDS Design Workflow — Snakemake

Rules:
  1. Build GDS files from Python design scripts
  2. Validate layouts (DRC-like checks)
  3. Generate layout reports (PNG previews)
"""

import glob
import os

# ── Config ──────────────────────────────────────────────────────────────────
DESIGNS_DIR = config.get("designs_dir", "designs")
GDS_DIR     = config.get("gds_dir", "gds")
REPORT_DIR  = config.get("report_dir", "reports")

# Auto-discover design scripts
DESIGNS = [os.path.splitext(os.path.basename(f))[0]
           for f in glob.glob(os.path.join(DESIGNS_DIR, "*.py"))]

# ── Rules ───────────────────────────────────────────────────────────────────

rule all:
    input:
        expand(os.path.join(REPORT_DIR, "{design}", "done"), design=DESIGNS),


rule build_gds:
    output:
        gds=os.path.join(GDS_DIR, "{design}.gds"),
        meta=os.path.join(GDS_DIR, "{design}.json"),
    params:
        script=os.path.join(DESIGNS_DIR, "{design}.py"),
    log:
        os.path.join(REPORT_DIR, "{design}", "build.log"),
    conda:
        "envs/gds.yaml"
    shell:
        """
        python -c "import os; os.makedirs('{GDS_DIR}', exist_ok=True); os.makedirs(os.path.dirname('{log}'), exist_ok=True)"
        python scripts/build_gds.py {params.script} \
            --output {output.gds} \
            --meta {output.meta} \
            > {log} 2>&1
        """


rule validate:
    input:
        gds=os.path.join(GDS_DIR, "{design}.gds"),
    output:
        os.path.join(REPORT_DIR, "{design}", "validate.ok"),
    log:
        os.path.join(REPORT_DIR, "{design}", "validate.log"),
    shell:
        """
        python scripts/validate.py {input.gds} > {log} 2>&1
        python -c "import pathlib; pathlib.Path('{output}').touch()"
        """


rule report:
    input:
        gds=os.path.join(GDS_DIR, "{design}.gds"),
        meta=os.path.join(GDS_DIR, "{design}.json"),
        valid=os.path.join(REPORT_DIR, "{design}", "validate.ok"),
    output:
        preview=os.path.join(REPORT_DIR, "{design}", "layout.png"),
        summary=os.path.join(REPORT_DIR, "{design}", "summary.json"),
        done=os.path.join(REPORT_DIR, "{design}", "done"),
    log:
        os.path.join(REPORT_DIR, "{design}", "report.log"),
    shell:
        """
        python scripts/report.py {input.gds} \
            --meta {input.meta} \
            --preview {output.preview} \
            --summary {output.summary} \
            > {log} 2>&1
        python -c "import pathlib; pathlib.Path('{output.done}').touch()"
        """
```

- [ ] **Step 6: Create envs/gds.yaml**

Create `/d/gds_argo/gds-template/envs/gds.yaml`:

```yaml
name: gds
channels:
  - conda-forge
dependencies:
  - python=3.12
  - pip
  - pip:
    - gdsfactory>=8.0
    - klayout
    - matplotlib
```

- [ ] **Step 7: Create requirements.txt**

Create `/d/gds_argo/gds-template/requirements.txt`:

```
gdsfactory>=8.0
klayout
matplotlib
snakemake
```

- [ ] **Step 8: Create designs/markers.py**

Create `/d/gds_argo/gds-template/designs/markers.py`:

```python
"""Four square markers for chip alignment.

Creates 20um x 20um square markers at positions (+/-1500, +/-1500).
"""
import gdsfactory as gf


def main():
    c = gf.Component("markers")

    size = 20.0
    positions = [
        (1500.0, 1500.0),
        (1500.0, -1500.0),
        (-1500.0, 1500.0),
        (-1500.0, -1500.0),
    ]

    for i, (x, y) in enumerate(positions):
        rect = gf.c.rectangle(size=(size, size), layer=(1, 0))
        ref = c << rect
        ref.movex(x - size / 2)
        ref.movey(y - size / 2)

    return c


if __name__ == "__main__":
    c = main()
    c.write_gds("markers.gds")
```

- [ ] **Step 9: Create scripts/build_gds.py**

Create `/d/gds_argo/gds-template/scripts/build_gds.py`:

```python
"""Build a GDS file from a Python design script.

Usage:
    python build_gds.py designs/mzi.py --output gds/mzi.gds --meta gds/mzi.json
"""
import argparse
import json
import os
import runpy
import sys
import traceback

import gdsfactory as gf

# Activate the generic PDK so gf.c.* components are available
gf.gpdk.PDK.activate()


def build(script_path: str, output: str, meta_path: str | None = None):
    module_name = os.path.splitext(os.path.basename(script_path))[0]
    script_dir = os.path.dirname(os.path.abspath(script_path))

    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    try:
        mod = runpy.run_path(script_path)
    except Exception:
        traceback.print_exc()
        sys.exit(1)

    # Look for a main() function, then component/design variable, then any callable returning a Component
    component = None
    if "main" in mod and callable(mod["main"]):
        component = mod["main"]()
    elif "component" in mod:
        comp = mod["component"]
        component = comp() if callable(comp) else comp
    elif "design" in mod:
        des = mod["design"]
        component = des() if callable(des) else des
    else:
        # Fallback: find first callable that takes no args and returns a Component-like object
        for name, obj in mod.items():
            if name.startswith("_") or not callable(obj):
                continue
            try:
                result = obj()
                if hasattr(result, 'write_gds'):
                    component = result
                    break
            except Exception:
                continue
    if component is None:
        print(f"ERROR: {script_path} must define main(), component, or a gdsfactory builder function", file=sys.stderr)
        sys.exit(1)

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    component.write_gds(output)
    print(f"Wrote {output}")

    if meta_path:
        info = {
            "script": script_path,
            "component": component.name,
            "ports": [str(p) for p in component.ports] if hasattr(component, 'ports') else [],
        }
        os.makedirs(os.path.dirname(meta_path) or ".", exist_ok=True)
        with open(meta_path, "w") as f:
            json.dump(info, f, indent=2)
        print(f"Wrote {meta_path}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("script", help="Path to design .py script")
    p.add_argument("--output", required=True, help="Output .gds path")
    p.add_argument("--meta", default=None, help="Output metadata .json path")
    args = p.parse_args()
    build(args.script, args.output, args.meta)
```

Note: This is the phononic-superconductor version **without** the broken `fix_gds_units` function.

- [ ] **Step 10: Create scripts/validate.py**

Create `/d/gds_argo/gds-template/scripts/validate.py`:

```python
"""Basic layout validation for a GDS file.

Checks: non-empty, bounding box within limits.
"""
import argparse
import sys

import klayout.db as kdb


def validate(gds_path: str, max_dim: float = 100_000) -> list[str]:
    layout = kdb.Layout()
    layout.read(gds_path)

    errors = []
    if layout.cells() == 0:
        errors.append("Layout has no cells")
        return errors

    top = layout.top_cell()
    if top is None:
        errors.append("No top cell found")
        return errors

    bbox = top.bbox()
    w = bbox.width() / 1000.0  # dbu -> um
    h = bbox.height() / 1000.0

    if w > max_dim or h > max_dim:
        errors.append(f"Layout too large: {w:.0f} x {h:.0f} um (max {max_dim})")

    if not errors:
        print(f"OK: {top.name} — {w:.1f} x {h:.1f} um")

    return errors


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("gds", help="Path to .gds file")
    p.add_argument("--max-dim", type=float, default=100_000)
    args = p.parse_args()
    errs = validate(args.gds, args.max_dim)
    for e in errs:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1 if errs else 0)
```

- [ ] **Step 11: Create scripts/report.py**

Create `/d/gds_argo/gds-template/scripts/report.py`:

```python
"""Generate a layout preview PNG and summary JSON for a GDS file."""
import argparse
import json
import os

import klayout.db as kdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def report(gds_path: str, meta_path: str | None, preview_path: str, summary_path: str):
    layout = kdb.Layout()
    layout.read(gds_path)
    top = layout.top_cell()

    if top is None:
        print("No top cell", file=sys.stderr)
        return

    # Extract cell info
    cells = []
    for ci in layout.each_cell():
        cells.append({
            "name": ci.name,
            "inst_count": ci.each_inst().__length_hint__() if hasattr(ci.each_inst(), '__length_hint__') else 0,
        })

    bbox = top.bbox()
    width_um = bbox.width() / 1000.0
    height_um = bbox.height() / 1000.0

    summary = {
        "gds": gds_path,
        "top_cell": top.name,
        "width_um": width_um,
        "height_um": height_um,
        "cell_count": layout.cells(),
        "cells": cells[:50],
    }

    if meta_path and os.path.exists(meta_path):
        with open(meta_path) as f:
            summary["build_meta"] = json.load(f)

    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote {summary_path}")

    # Generate preview image via klayout
    os.makedirs(os.path.dirname(preview_path), exist_ok=True)
    try:
        lv = kdb.LayoutView()
        lv.load_layout(gds_path)
        lv.max_hier()
        lv.save_image(preview_path, 800, 600)
        print(f"Wrote {preview_path}")
    except Exception:
        # Fallback: simple matplotlib placeholder
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, f"{top.name}\n{width_um:.1f} x {height_um:.1f} um",
                ha="center", va="center", fontsize=14)
        fig.savefig(preview_path, dpi=100)
        plt.close(fig)
        print(f"Wrote {preview_path} (placeholder)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("gds", help="Path to .gds file")
    p.add_argument("--meta", default=None)
    p.add_argument("--preview", required=True)
    p.add_argument("--summary", required=True)
    args = p.parse_args()
    report(args.gds, args.meta, args.preview, args.summary)
```

- [ ] **Step 12: Commit and push to Gitea**

Create the repo on Gitea first (same pattern as Task 1 — use org or user):

```bash
curl -s -X POST \
  -H "Authorization: token $GITEA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"gds-template","description":"Standard GDS photonic design project template","private":false,"auto_init":false}' \
  "http://localhost:3000/api/v1/user/repos"
```

Then commit and push:

```bash
cd /d/gds_argo/gds-template
git add .
git commit -m "feat: initial GDS project template with markers, build pipeline, and agent instructions"
git remote add origin ssh://git@localhost:2222/{owner}/gds-template.git
git push -u origin main
```

Where `{owner}` is the org or username from the repo creation step.

---

### Task 3: Add gds-template as Submodule in gitea Repo

**Files:**
- Modify: `gitea/.gitmodules` (auto-updated by git submodule add)

- [ ] **Step 1: Add the submodule**

```bash
cd /d/gds_argo/Gdslab/gitea
git submodule add ssh://git@localhost:2222/{owner}/gds-template.git gds-template
```

Where `{owner}` matches where the template repo was pushed.

- [ ] **Step 2: Commit the submodule addition**

```bash
cd /d/gds_argo/Gdslab/gitea
git add .gitmodules gds-template
git commit -m "feat: add gds-template as submodule"
```

---

### Task 4: Verification

**Files:** None (testing only)

- [ ] **Step 1: Verify gds-agent-skill repo on Gitea**

```bash
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/gds-agent-skill/contents/.claude/skills/gds-agent.md" \
  | python -m json.tool | head -5
```

Expected: JSON response with `"content"` field containing the skill file.

- [ ] **Step 2: Verify gds-template repo on Gitea**

```bash
curl -s -H "Authorization: token $GITEA_TOKEN" \
  "http://localhost:3000/api/v1/repos/{owner}/gds-template/contents/" \
  | python -m json.tool | grep '"name"'
```

Expected: List of files including `CLAUDE.md`, `Snakefile`, `config.yaml`, `designs/`, `scripts/`, `envs/`.

- [ ] **Step 3: Verify submodule in gitea repo**

```bash
cd /d/gds_argo/Gdslab/gitea
git submodule status
```

Expected: One line showing `gds-template` with a commit hash.

- [ ] **Step 4: Verify the skill install URL works**

```bash
curl -s -o /dev/null -w "%{http_code}" \
  "http://localhost:3000/{owner}/gds-agent-skill/raw/branch/main/.claude/skills/gds-agent.md"
```

Expected: `200`.

- [ ] **Step 5: Verify template builds**

```bash
cd /d/gds_argo/gds-template
snakemake --cores 4
ls -la gds/
```

Expected: `gds/markers.gds` and `gds/markers.json` created, build succeeds.

---

## Self-Review

**Spec coverage:**
- [x] gds-agent-skill repo with skill file + README → Task 1
- [x] gds-template repo with clean project structure → Task 2
- [x] Template excludes agent/ CLI → Task 2 (not included)
- [x] Template excludes example_mzi.py → Task 2 (only markers.py included)
- [x] CLAUDE.md with skill install instructions → Task 2 Step 2
- [x] Submodule link in gitea project → Task 3
- [x] Verification steps → Task 4

**Placeholder scan:** No TBD/TODO found. All steps have complete file contents and commands. The `{owner}` placeholder in URLs is a variable that resolves at execution time based on Gitea org/user setup.

**Type consistency:** File names and paths are consistent across all tasks. The skill install URL in CLAUDE.md (`$GITEA_URL/GdsLab/gds-agent-skill/raw/branch/main/.claude/skills/gds-agent.md`) matches the repo structure in Task 1.
