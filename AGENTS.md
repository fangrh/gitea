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
