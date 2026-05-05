# GDS Services Split — Design Spec

**Date:** 2026-05-05
**Status:** DRAFT

## Problem

Every GDS viewer or builder change requires a full Gitea Docker rebuild (~15 min). The GDS parser and builder iterate rapidly — the viewer needs rendering fixes, the builder tracks the forked gdsfactory.

## Solution

Split into three Docker services in the same `docker-compose.yml`:

```
                    ┌──────────────────┐
                    │      Gitea       │  :3000 (public)
                    │  template, nav,  │
                    │  file list, auth │
                    └────┬─────────┬───┘
                         │ proxy   │ proxy
              ┌──────────▼──┐  ┌──▼──────────────┐
              │ gds-parser  │  │  gds-builder     │
              │   :8000     │  │    :8001         │
              │ klayout/GDS │  │ fork gdsfactory  │
              │  → GeoJSON  │  │ .py scripts →GDS │
              └─────────────┘  └──────────────────┘
```

Internal network: all services on `gitea` bridge network. Only Gitea exposes ports (3000, 2222).

---

## Service 1: gds-parser (new)

**Role:** Read `.gds` files from a git repo and return GeoJSON.

**Stack:** Python 3.12 + FastAPI + klayout

**API:**
```
GET /health          → {"status": "ok"}
GET /parse           → GeoJSON FeatureCollection
  ?repo=owner/repo
  &ref=main
  &path=gds/example.gds
```

**Implementation:**
- Uses klayout's `kdb.Layout().read()` to parse GDSII (handles all GDS variants)
- Flattens cell hierarchy, groups polygons by layer
- Returns GeoJSON with per-layer coloring
- Clones repo via SSH (shared volume with Gitea's git repos, or git clone on demand)

**Dockerfile:** `python:3.12-slim`, `pip install fastapi uvicorn klayout httpx`

**Rebuild:** `docker compose up -d --build gds-parser` (~30 sec)

---

## Service 2: gds-builder (new)

**Role:** Build `.gds` files from design Python scripts using the forked gdsfactory.

**Stack:** Python 3.12 + FastAPI + forked gdsfactory + snakemake

**API:**
```
GET  /health           → {"status": "ok"}
POST /build            → {"status": "ok", "gds_files": [...]}
  ?repo=owner/repo
  &ref=main
  &design=markers      # optional: build a specific design
POST /build/all        → rebuild all designs in the repo
```

**Implementation:**
- Clones/updates the repo via SSH
- Runs `snakemake --cores 4` or `build_gds.py` per design
- Patches broken klayout UNITS (if still needed)
- Commits built GDS files and pushes back
- Uses the forked gdsfactory submodule at `gdsfactory/`

**Dockerfile:** `python:3.12-slim`, `pip install fastapi uvicorn gdsfactory klayout snakemake`

**Rebuild:** `docker compose up -d --build gds-builder` (~30 sec)

---

## Service 3: Gitea (modified)

**Role:** Keep the GDS Viewer tab, file listing, and page template. The `/gds/data` handler becomes a thin proxy.

**Changes:**
- `routers/web/repo/gds.go`: replace the `GDSViewerData` handler with an HTTP proxy to `http://gds-parser:8000/parse`
- Remove `modules/gdsviewer/` (parser + geojson moved to gds-parser)
- `templates/repo/gds.tmpl`: unchanged
- `templates/repo/header.tmpl`: unchanged
- `routers/web/web.go`: route unchanged
- `GDSViewer` (page handler): unchanged (lists .gds files)

**Benefit:** Gitea no longer needs the GDSII parser compiled in. Template-only changes still require Gitea rebuild, but these are rare.

---

## docker-compose.yml

```yaml
services:
  db:        # unchanged
  gitea:     # unchanged (builds from local Dockerfile)
  
  gds-parser:
    build:
      context: ./gds-services/parser
    restart: unless-stopped
    networks:
      - gitea
    volumes:
      - gitea-data:/data:ro  # read-only access to git repos
  
  gds-builder:
    build:
      context: ./gds-services/builder
    restart: unless-stopped
    networks:
      - gitea
    volumes:
      - gitea-data:/data  # read-write access to git repos
    environment:
      GITEA_TOKEN: ${GITEA_TOKEN}
```

---

## Open Questions

- **Repo access:** Should services clone via SSH or share the Gitea git volume? Volume sharing is faster but couples to Gitea internals. SSH cloning is more portable.
- **gds-builder trigger:** Webhook from Gitea on push? Or manual API call from the agent CLI?
- **gds-parser caching:** Should parsed GeoJSON be cached? For large GDS files, parsing can be slow.

## NOT in scope

- CI/CD pipeline for auto-build on push (existing `.gitea/workflows/build-gds.yml` handles this)
- Moving the OpenLayers viewer frontend out of Gitea (template stays in Gitea)
