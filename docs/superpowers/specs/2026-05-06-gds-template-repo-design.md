# GDS Template Repo — Design Spec

## Context

New users need a starting point for GDS design projects on Gitea. The phononic-superconductor repo has the right structure but contains project-specific content and an obsolete `agent/` CLI. We need a clean template that any user can fork/copy, plus a shared skill repo so all users can install `/gds-agent`.

## Architecture

```
Gitea Server
├── GdsLab/gds-agent-skill/     ← shared skill definition (public)
│   └── .claude/skills/gds-agent.md
│   └── README.md
│
├── GdsLab/gds-template/        ← template for new GDS projects
│   ├── designs/markers.py      ← one example design
│   ├── scripts/                ← build pipeline (build_gds.py, validate.py, report.py)
│   ├── Snakefile               ← snakemake workflow
│   ├── config.yaml
│   ├── envs/gds.yaml
│   ├── requirements.txt
│   ├── CLAUDE.md               ← install instructions for /gds-agent
│   └── .gitignore
│
└── {user}/{project}/           ← user's repo (created from template)
    ├── .claude/skills/gds-agent.md  ← copied from gds-agent-skill
    ├── ... (template content)

gitea project repo (this repo)
└── gds-template/               ← git submodule → GdsLab/gds-template
```

## Component 1: gds-agent-skill repo

**Location:** `GdsLab/gds-agent-skill` on Gitea server

**Purpose:** Single source of truth for the `/gds-agent` skill. All users reference this.

### Files

```
gds-agent-skill/
├── .claude/
│   └── skills/
│       └── gds-agent.md    ← identical to gitea repo's .claude/skills/gds-agent.md
└── README.md               ← one-command install instructions
```

### README.md content

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

## How it works

The skill polls Gitea for open issues labeled 'gds', parses provenance metadata,
modifies the referenced design script, runs snakemake to verify, pushes a fix branch,
opens a PR, and replies to the issue.

## Requirements

- Claude Code installed
- Gitea API token with repo read/write access
- Git remote origin pointing to Gitea
- snakemake + gdsfactory installed locally
```

## Component 2: gds-template repo

**Location:** `GdsLab/gds-template` on Gitea server

**Purpose:** Standard project structure for new photonic design repos. Users create repos from this template on Gitea.

### Files

```
gds-template/
├── .gitignore
├── CLAUDE.md
├── config.yaml
├── envs/
│   └── gds.yaml
├── designs/
│   └── markers.py           ← alignment markers example
├── scripts/
│   ├── build_gds.py
│   ├── validate.py
│   └── report.py
├── Snakefile
└── requirements.txt
```

### What's included (from phononic-superconductor)

- `scripts/build_gds.py` — Python → GDS compiler (without the broken `fix_gds_units`)
- `scripts/validate.py` — layout validation
- `scripts/report.py` — preview generation
- `Snakefile` — snakemake workflow (build → validate → report)
- `config.yaml` — workflow configuration
- `envs/gds.yaml` — conda environment spec
- `requirements.txt` — Python dependencies
- `designs/markers.py` — one example design (alignment markers)

### What's excluded (from phononic-superconductor)

- `agent/` directory — obsolete CLI tool, replaced by `/gds-agent` skill
- `designs/example_mzi.py` — project-specific design, not generic
- `.gitea/` directory — Gitea config specific to that repo
- `.worktrees/` — working state
- `.snakemake/` — runtime state
- `AGENT.md` — replaced by CLAUDE.md with skill install instructions

### CLAUDE.md content

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

Set your Gitea token: `export GITEA_TOKEN=your-token`

Run in Claude Code: `/gds-agent`

## Design Conventions

- Place design scripts in `designs/` (one component per file)
- Each script must define `main()`, `component`, or a callable returning a gdsfactory Component
- File name determines output GDS name: `designs/markers.py` → `gds/markers.gds`
- Run `snakemake --cores 4` before committing to verify builds pass
```

### .gitignore content

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

## Component 3: Submodule link

The gitea project repo (`D:\gds_argo\Gdslab\gitea`) adds `gds-template` as a submodule:

```bash
cd D:\gds_argo\Gdslab\gitea
git submodule add {gitea_url}/GdsLab/gds-template.git gds-template
git commit -m "feat: add gds-template as submodule"
```

This lets the gitea project track template updates and potentially use it for automated repo initialization.

## Implementation Steps

1. Create `gds-agent-skill` repo on Gitea (`GdsLab/gds-agent-skill`)
   - Push `.claude/skills/gds-agent.md` (copy from gitea repo)
   - Push `README.md` with install instructions

2. Create `gds-template` repo on Gitea (`GdsLab/gds-template`)
   - Copy files from phononic-superconductor (exclude agent/, .gitea/, .worktrees/, example_mzi.py)
   - Create clean CLAUDE.md with skill install instructions
   - Create clean .gitignore

3. Add `gds-template` as submodule in gitea project repo
   - `git submodule add` in gitea repo

## Self-Review

**Placeholder scan:** No TBD/TODO. All file contents specified.

**Internal consistency:**
- CLAUDE.md references `$GITEA_URL/GdsLab/gds-agent-skill/raw/branch/main/.claude/skills/gds-agent.md` — consistent with gds-agent-skill repo structure
- gds-agent.md in skill repo is identical to `.claude/skills/gds-agent.md` in gitea project repo
- Template excludes agent/ CLI but includes scripts/ (build_gds.py needs it for snakemake)

**Scope check:** Three clear deliverables (skill repo, template repo, submodule link). No overlap.

**Ambiguity check:** "Clean slate from phononic-superconductor" means copy the files listed above, not fork. The template is a new repo with cherry-picked files.
