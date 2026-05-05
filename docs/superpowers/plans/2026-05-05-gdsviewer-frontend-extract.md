# GDS Viewer Frontend Extract — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the GDS viewer OpenLayers frontend from Gitea's template into the gds-parser container, so UI changes rebuild in ~7s instead of 15min.

**Architecture:** Gitea `gds.tmpl` becomes a thin iframe → `http://gds-parser:8000/viewer?repo=...&branch=...`. The full OpenLayers viewer (HTML/JS/CSS) lives in gds-parser. Gitea only handles the nav tab and iframe wrapper.

**Tech Stack:** Python FastAPI static file serving + embedded HTML template

---

### Task 1: Add self-contained viewer page to gds-parser

**Files:**
- Create: `gds-services/parser/viewer.html`
- Modify: `gds-services/parser/main.py`

- [ ] **Step 1: Create viewer.html with full OpenLayers viewer**

Write `gds-services/parser/viewer.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GDS Viewer</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/ol@10/ol.css">
<script src="https://cdn.jsdelivr.net/npm/ol@10/dist/ol.js"></script>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { display: flex; height: 100vh; background: #1a1a2e; font-family: sans-serif; }
#sidebar { width: 220px; background: #1e1e2e; color: #cdd6f4; overflow-y: auto; padding: 12px; flex-shrink: 0; }
#sidebar h4 { margin: 0 0 8px 0; color: #89b4fa; }
#sidebar button { width: 100%; margin-bottom: 8px; padding: 6px 10px; background: #45475a; color: #cdd6f4; border: 1px solid #585b70; border-radius: 4px; cursor: pointer; font-size: 12px; }
#sidebar button:hover { background: #585b70; }
#map { flex-grow: 1; min-height: 500px; }
.file-item { padding: 6px 8px; cursor: pointer; border-radius: 4px; margin-bottom: 2px; font-size: 13px; word-break: break-all; }
.file-item:hover { background: #313244; }
.file-item.active { background: #45475a; }
.legend-row { display: flex; align-items: center; gap: 6px; padding: 3px 0; font-size: 12px; cursor: pointer; }
.swatch { width: 14px; height: 14px; border-radius: 2px; flex-shrink: 0; }
.swatch.hidden { opacity: 0.2; }
</style>
</head>
<body>
<div id="sidebar">
    <h4>GDS Files</h4>
    <button onclick="fitView()">Fit View</button>
    <div id="file-list"><p style="color:#6c7086;font-size:13px;">Loading...</p></div>
</div>
<div id="map"></div>

<script>
const params = new URLSearchParams(window.location.search);
const repo = params.get('repo') || '';
const branch = params.get('branch') || 'main';

var source = new ol.source.Vector();
var vectorLayer = new ol.layer.Vector({
    source: source,
    style: function(feature) {
        var color = feature.get('color') || '#fff';
        var visible = feature.get('visible') !== false;
        if (!visible) return new ol.style.Style({});
        return new ol.style.Style({
            stroke: new ol.style.Stroke({ color: color, width: 1 }),
            fill: new ol.style.Fill({ color: color + '80' })
        });
    }
});

var map = new ol.Map({
    target: 'map',
    layers: [vectorLayer],
    view: new ol.View({ center: [0, 0], zoom: 0, minZoom: -20, maxZoom: 40 }),
    controls: [new ol.control.Zoom()]
});

var allFeatures = [];
var layerColors = {};

function fitView() {
    var extent = source.getExtent();
    if (extent && isFinite(extent[0])) {
        map.getView().fit(extent, { padding: [40, 40, 40, 40], duration: 300 });
    }
}

function loadGDS(filePath) {
    fetch('/data?repo=' + encodeURIComponent(repo) + '&ref=' + branch + '&path=' + encodeURIComponent(filePath))
        .then(function(r) { if (!r.ok) throw Error('HTTP ' + r.status); return r.json(); })
        .then(function(geojson) {
            source.clear();
            allFeatures = [];
            layerColors = {};
            geojson.features.forEach(function(feature) {
                var layerId = feature.properties.layer;
                var dataType = feature.properties.data_type;
                var color = feature.properties.color;
                var key = layerId + '/' + dataType;
                layerColors[key] = color;
                var polys = feature.geometry.coordinates;
                polys.forEach(function(polygon) {
                    polygon.forEach(function(ring) {
                        var geom = new ol.geom.Polygon([ring]);
                        var f = new ol.Feature({ geometry: geom });
                        f.set('layer', key);
                        f.set('color', color);
                        f.set('layerKey', key);
                        f.set('visible', true);
                        allFeatures.push(f);
                        source.addFeature(f);
                    });
                });
            });
            if (allFeatures.length > 0) fitView();
            buildLegend();
        }).catch(function(e) { console.error('Load failed: ' + e.message); });
}

function buildLegend() {
    var existing = document.querySelector('.legend-section');
    if (existing) existing.remove();
    var keys = Object.keys(layerColors);
    if (!keys.length) return;
    var div = document.createElement('div');
    div.className = 'legend-section';
    div.style.marginTop = '12px';
    div.innerHTML = '<h4 style="margin:0 0 6px 0;color:#89b4fa;">Layers</h4>';
    keys.forEach(function(key) {
        var row = document.createElement('div');
        row.className = 'legend-row';
        row.innerHTML = '<span class="swatch" style="background:' + layerColors[key] + ';" data-key="' + key + '"></span> ' + key;
        row.onclick = function() {
            var swatch = row.querySelector('.swatch');
            var hidden = swatch.classList.toggle('hidden');
            allFeatures.forEach(function(f) {
                if (f.get('layerKey') === key) f.set('visible', !hidden);
            });
            vectorLayer.changed();
        };
        div.appendChild(row);
    });
    document.getElementById('sidebar').appendChild(div);
}

// Load file list from API
fetch('/files?repo=' + encodeURIComponent(repo) + '&ref=' + branch)
    .then(function(r) { return r.json(); })
    .then(function(files) {
        var list = document.getElementById('file-list');
        list.innerHTML = '';
        if (!files || !files.length) {
            list.innerHTML = '<p style="color:#6c7086;font-size:13px;">No .gds files found.</p>';
            return;
        }
        files.forEach(function(f) {
            var div = document.createElement('div');
            div.className = 'file-item';
            div.textContent = f;
            div.onclick = function() {
                document.querySelectorAll('.file-item.active').forEach(function(el) { el.classList.remove('active'); });
                div.classList.add('active');
                loadGDS(f);
            };
            list.appendChild(div);
        });
        // Auto-load first file
        setTimeout(function() {
            var el = document.querySelector('.file-item');
            if (el) el.click();
        }, 200);
    }).catch(function(e) { console.error('File list failed: ' + e.message); });
</script>
</body>
</html>
```

- [ ] **Step 2: Add viewer and file-list endpoints to main.py**

Edit `gds-services/parser/main.py` — add these endpoints:

```python
from fastapi.responses import HTMLResponse, FileResponse

@app.get("/viewer")
def viewer():
    """Serve the GDS viewer HTML page."""
    return FileResponse("viewer.html", media_type="text/html")


@app.get("/files")
def list_files(repo: str, ref: str = "main"):
    """List .gds files in a repo by scanning the git data volume."""
    owner, name = repo.split("/")
    repo_dir = pathlib.Path(f"/data/git/repositories/{owner.lower()}/{name.lower()}.git")
    # Use git to list tree
    import subprocess, os
    tree = subprocess.run(
        ["git", "--git-dir", str(repo_dir), "ls-tree", "-r", "--name-only", ref],
        capture_output=True, text=True
    )
    files = [f.strip() for f in tree.stdout.splitlines() if f.strip().endswith(".gds")]
    return files


@app.get("/data")
def get_gds_data(repo: str, ref: str = "main", path: str = ""):
    """Read a GDS file from the repo and return GeoJSON."""
    owner, name = repo.split("/")
    repo_dir = pathlib.Path(f"/data/git/repositories/{owner.lower()}/{name.lower()}.git")
    import subprocess
    result = subprocess.run(
        ["git", "--git-dir", str(repo_dir), "show", f"{ref}:{path}"],
        capture_output=True
    )
    if result.returncode != 0:
        raise HTTPException(404, f"File not found: {path}")
    return Response(
        content=json.dumps(parse_gds(result.stdout)),
        media_type="application/json"
    )
```

Add `import pathlib` at the top.

- [ ] **Step 3: Copy viewer.html into Docker image**

The Dockerfile already copies `main.py`. Add viewer.html:
Edit `gds-services/parser/Dockerfile` — change `COPY main.py .` to `COPY main.py viewer.html .`

- [ ] **Step 4: Rebuild and test**

```bash
docker compose up -d --build gds-parser
# Expected: ~10s rebuild
```

Test:
```bash
curl http://gds-parser:8000/viewer?repo=RuihuanFang/phononic-superconductor
# Expected: HTML page with GDS viewer
```

- [ ] **Step 5: Commit**

```bash
git add gds-services/parser/
git commit -m "feat(gds-parser): add self-contained viewer page with file list and data API"
```

---

### Task 2: Simplify Gitea template to iframe

**Files:**
- Modify: `templates/repo/gds.tmpl`

- [ ] **Step 1: Replace gds.tmpl with iframe wrapper**

Write `templates/repo/gds.tmpl`:

```html
{{template "base/head" .}}
<div role="main" aria-label="{{.Title}}" class="page-content repository gds-viewer">
    {{template "repo/header" .}}
    <iframe
        src="http://gds-parser:8000/viewer?repo={{.Repository.FullName}}&branch={{.BranchName}}"
        style="width:100%; flex-grow:1; border:none; min-height:600px;"
        allow="fullscreen"
        sandbox="allow-scripts allow-same-origin"
        title="GDS Viewer"
    ></iframe>
</div>
<style>.gds-viewer { display:flex; flex-direction:column; } .gds-viewer iframe { flex-grow:1; }</style>
{{template "base/footer" .}}
```

Note: The iframe loads from `http://gds-parser:8000/viewer` — this is the internal Docker network URL. The browser resolves this through Gitea's reverse proxy or directly if the port is exposed. Since we only expose port 3000, we need Gitea to proxy `/viewer` requests to gds-parser.

- [ ] **Step 2: Add Gitea reverse proxy route for viewer**

Actually, the simpler approach: the iframe URL should use a path that Gitea proxies. Add a proxy route in `routers/web/web.go`:

```go
// Proxy viewer page to gds-parser
m.Get("/gds/viewer", func(ctx *context.Context) {
    resp, err := http.Get(setting.GDSViewer.ParserURL + "/viewer?" + ctx.Req.URL.RawQuery)
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
})
```

And change the iframe src to: `{{.RepoLink}}/gds/viewer?repo={{.Repository.FullName}}&branch={{.BranchName}}`

But this requires a Gitea rebuild (15min). For now, the simplest approach:

- [ ] **Step 1 (simplified): Use Gitea iframe with viewer.html served from gds-parser via port exposure**

Actually the cleanest approach: expose gds-parser port 8000 to localhost only, so the browser can access it directly. Update docker-compose.yml:

```yaml
  gds-parser:
    ...
    ports:
      - "127.0.0.1:8000:8000"
```

Then the iframe src is `http://localhost:8000/viewer?...`

- [ ] **Step 3: Commit**

```bash
git add templates/repo/gds.tmpl docker-compose.yml
git commit -m "refactor(gdsviewer): iframe to gds-parser viewer, remove embedded JS"
```

---

### Task 3: Rebuild and verify

- [ ] **Step 1: Rebuild Gitea and gds-parser**

```bash
docker compose up -d --build
# This is the LAST 15-minute Gitea rebuild for GDS viewer changes
```

- [ ] **Step 2: Verify viewer loads**

```bash
curl http://localhost:3000/RuihuanFang/phononic-superconductor/gds
# Expected: 200, page with iframe
```

- [ ] **Step 3: Verify zoom buttons work**

Open browser → GDS Viewer tab → +/- buttons visible and functional

- [ ] **Step 4: Verify Fit View works**

Click Fit View button → layout zooms to fit

- [ ] **Step 5: Verify fast iteration**

Make a CSS change in `gds-services/parser/viewer.html`:
```bash
docker compose up -d --build gds-parser   # ~7 seconds
```
Refresh browser → change visible immediately.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "fix: final integration after viewer extraction"
```
