# GDS Services Split — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split GDS parser and builder into separate Docker services for independent rebuild (~30s vs 15min Gitea rebuild).

**Architecture:** Three services on `gitea` network. Gitea proxies `/gds/data` → `gds-parser:8000`. Only Gitea exposes port 3000.

**Tech Stack:** Python 3.12 + FastAPI + klayout (parser), Python 3.12 + FastAPI + fork gdsfactory (builder), Go proxy (Gitea).

---

### Task 1: gds-parser service

**Files:**
- Create: `gds-services/parser/Dockerfile`
- Create: `gds-services/parser/requirements.txt`
- Create: `gds-services/parser/main.py`

- [ ] **Step 1: Create Dockerfile and requirements**

```bash
mkdir -p gds-services/parser
```

Write `gds-services/parser/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Write `gds-services/parser/requirements.txt`:
```
fastapi==0.115.0
uvicorn==0.30.0
klayout==0.30.8
```

- [ ] **Step 2: Write main.py**

Write `gds-services/parser/main.py`:
```python
"""GDS Parser Service — parses .gds files into GeoJSON using klayout."""
import io
import json
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response

app = FastAPI(title="gds-parser")

LAYER_COLORS = [
    "#4ecdc4", "#ff6b6b", "#45b7d1", "#96ceb4",
    "#ffeaa7", "#dfe6e9", "#fd79a8", "#a29bfe",
    "#6c5ce7", "#00b894", "#e17055", "#0984e3",
    "#fab1a0", "#81ecec", "#55efc4", "#74b9ff",
]


def parse_gds(data: bytes) -> dict:
    """Parse GDSII binary and return GeoJSON FeatureCollection."""
    import klayout.db as kdb
    layout = kdb.Layout()
    layout.read(io.BytesIO(data))

    layers = {}
    for cell in layout.each_cell():
        for li in layout.layer_indexes():
            it = cell.shapes(li)
            if it.is_empty():
                continue
            info = layout.layer_infos()[li]
            ln = info.layer
            if ln not in layers:
                layers[ln] = []
            region = kdb.Region(it)
            region.merge()
            for poly in region.each():
                pts = poly.to_simple_polygon()
                ring = [[p.x * layout.dbu, p.y * layout.dbu] for p in pts.each_point()]
                if len(ring) >= 3:
                    ring.append(ring[0])
                    layers[ln].append([ring])

    features = []
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for ln, polys in layers.items():
        if not polys:
            continue
        color = LAYER_COLORS[ln % len(LAYER_COLORS)]
        features.append({
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": polys},
            "properties": {"layer": ln, "data_type": 0, "color": color},
        })
        for poly in polys:
            for ring in poly:
                for x, y in ring:
                    min_x = min(min_x, x); max_x = max(max_x, x)
                    min_y = min(min_y, y); max_y = max(max_y, y)

    result = {"type": "FeatureCollection", "features": features}
    if features:
        result["bbox"] = [min_x, min_y, max_x, max_y]
    return result


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/parse")
async def parse_gds_post(request: Request):
    """Receive raw GDSII bytes, return GeoJSON."""
    data = await request.body()
    if not data:
        raise HTTPException(400, "Empty body")
    try:
        geojson = parse_gds(data)
    except Exception as e:
        raise HTTPException(422, f"Parse error: {e}")
    return Response(content=json.dumps(geojson), media_type="application/json")
```

- [ ] **Step 3: Build and smoke test**

```bash
docker build -t gds-parser gds-services/parser/
docker run --rm -d -p 8000:8000 --name gds-parser-test gds-parser
sleep 2
curl http://localhost:8000/health
# Expected: {"status":"ok"}
docker stop gds-parser-test
```

- [ ] **Step 4: Commit**

```bash
git add gds-services/parser/
git commit -m "feat: add gds-parser service — klayout FastAPI GDS→GeoJSON"
```

---

### Task 2: Gitea proxy + remove old module

**Files:**
- Modify: `routers/web/repo/gds.go`
- Modify: `modules/setting/gds_viewer.go`
- Remove: `modules/gdsviewer/parser.go`, `modules/gdsviewer/geojson.go`

- [ ] **Step 1: Update config to add ParserURL**

Edit `modules/setting/gds_viewer.go`:
```go
var (
    GDSViewer = struct {
        Enabled   bool
        IframeURL string
        ParserURL string
    }{
        Enabled: false,
    }
)

func loadGDSViewerFrom(rootCfg ConfigProvider) {
    sec, _ := rootCfg.GetSection("gds_viewer")
    if sec == nil {
        return
    }
    GDSViewer.Enabled = sec.Key("ENABLED").MustBool(false)
    GDSViewer.IframeURL = sec.Key("IFRAME_URL").MustString("")
    GDSViewer.ParserURL = sec.Key("PARSER_URL").MustString("http://gds-parser:8000")
}
```

- [ ] **Step 2: Rewrite GDSViewerData as proxy**

Edit `routers/web/repo/gds.go` — replace the GDSViewerData function and remove gdsviewer imports:
```go
import (
    "io"
    "net/http"
    // ... keep existing imports, remove "code.gitea.io/gitea/modules/gdsviewer"
)

// GDSViewerData proxies to gds-parser service
func GDSViewerData(ctx *context.Context) {
    if !setting.GDSViewer.Enabled {
        ctx.NotFound(nil)
        return
    }
    filePath := ctx.PathParam("filepath")
    if filePath == "" || !strings.HasSuffix(strings.ToLower(filePath), ".gds") {
        ctx.JSON(http.StatusBadRequest, map[string]string{"error": "invalid file path"})
        return
    }

    // Read raw GDS blob from git
    branchName := ctx.Repo.BranchName
    if branchName == "" {
        branchName = ctx.Repo.Repository.DefaultBranch
    }
    commit, err := ctx.Repo.GitRepo.GetBranchCommit(branchName)
    if err != nil {
        ctx.ServerError("GetBranchCommit", err)
        return
    }
    blob, err := commit.Tree.GetBlobByPath(filePath)
    if err != nil {
        ctx.ServerError("GetBlobByPath", err)
        return
    }
    reader, err := blob.DataAsync()
    if err != nil {
        ctx.ServerError("DataAsync", err)
        return
    }
    defer reader.Close()

    // Proxy to gds-parser
    resp, err := http.Post(setting.GDSViewer.ParserURL+"/parse", "application/octet-stream", reader)
    if err != nil {
        ctx.ServerError("gds-parser unreachable", err)
        return
    }
    defer resp.Body.Close()
    for k, vs := range resp.Header {
        for _, v := range vs {
            ctx.Resp.Header().Set(k, v)
        }
    }
    ctx.Resp.WriteHeader(resp.StatusCode)
    io.Copy(ctx.Resp, resp.Body)
}
```

- [ ] **Step 3: Remove old gdsviewer module**

```bash
rm modules/gdsviewer/parser.go modules/gdsviewer/geojson.go
# If directory empty: rmdir modules/gdsviewer
```

- [ ] **Step 4: Commit**

```bash
git add routers/web/repo/gds.go modules/setting/gds_viewer.go
git rm modules/gdsviewer/parser.go modules/gdsviewer/geojson.go 2>/dev/null
git commit -m "refactor: proxy /gds/data to gds-parser, remove Go GDSII parser"
```

---

### Task 3: gds-builder service stub

**Files:**
- Create: `gds-services/builder/Dockerfile`
- Create: `gds-services/builder/requirements.txt`
- Create: `gds-services/builder/main.py`

- [ ] **Step 1: Create files**

```bash
mkdir -p gds-services/builder
```

Write `gds-services/builder/Dockerfile`:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py .
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
```

Write `gds-services/builder/requirements.txt`:
```
fastapi==0.115.0
uvicorn==0.30.0
klayout==0.30.8
gdsfactory
snakemake
```

Write `gds-services/builder/main.py`:
```python
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
    """Build one design → GDS. Full pipeline in next iteration."""
    owner, name = repo.split("/")
    path = REPOS_DIR / owner.lower() / f"{name.lower()}.git"
    if not path.exists():
        raise HTTPException(404, f"Repo not found: {repo}")
    return {"status": "not_implemented", "message": "Builder stub — full pipeline next"}
```

- [ ] **Step 2: Commit**

```bash
git add gds-services/builder/
git commit -m "feat: add gds-builder service stub"
```

---

### Task 4: Update docker-compose.yml

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Add new services**

Edit `docker-compose.yml` — add after the gitea service block:
```yaml
  gds-parser:
    build:
      context: ./gds-services/parser
    restart: unless-stopped
    networks:
      - gitea
    volumes:
      - gitea-data:/data:ro

  gds-builder:
    build:
      context: ./gds-services/builder
    restart: unless-stopped
    networks:
      - gitea
    volumes:
      - gitea-data:/data
```

Add to gitea service environment:
```yaml
      GITEA__gds_viewer__PARSER_URL: "http://gds-parser:8000"
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add gds-parser and gds-builder to docker-compose"
```

---

### Task 5: Full rebuild and integration test

- [ ] **Step 1: Rebuild everything**

```bash
docker compose up -d --build
```

- [ ] **Step 2: Verify GDS viewer page loads**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000/RuihuanFang/phononic-superconductor/gds
# Expected: 200
```

- [ ] **Step 3: Verify GDS data flows through proxy→parser**

```bash
curl -s "http://localhost:3000/RuihuanFang/phononic-superconductor/gds/data/gds%2Fmarkers.gds" | python -c "import sys,json; d=json.load(sys.stdin); print('Features:', len(d['features']), 'Bbox:', d.get('bbox'))"
# Expected: Features: 1+ Bbox: [minX, minY, maxX, maxY]
```

- [ ] **Step 4: Verify independent gds-parser rebuild**

```bash
# Make a trivial change to gds-services/parser/main.py (e.g., add a comment)
docker compose up -d --build gds-parser
# Expected: only gds-parser rebuilds, Gitea untouched, <60 seconds
```

- [ ] **Step 5: Verify gds-parser health endpoint**

```bash
docker compose exec gds-parser curl -s http://localhost:8000/health
# Expected: {"status":"ok"}
```

- [ ] **Step 6: Commit any final fixes**

```bash
git add -A && git commit -m "fix: integration adjustments after service split"
```
