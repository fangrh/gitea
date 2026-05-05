# GDS Viewer — Polygon Inspection & Provenance Tracing

**Goal:** Click any polygon in the GDS viewer → see its full provenance (which file/function/line/class created it, for-loop iteration index, coordinates, area), with a one-click YAML copy button for filing issues.

**Architecture:** Four-layer pipeline: gdsfactory fork injects call-stack provenance into GDS PROPATTR → gds-parser extracts PROPATTR into GeoJSON properties → viewer.html renders click-to-inspect + console panel + YAML export → gds-builder runs isolated builds from bare repo (no clone).

**Tech Stack:** Python inspect + klayout PROPATTR (gdsfactory fork), klayout db.Layout properties (parser), OpenLayers 10 + vanilla JS (viewer), FastAPI + git plumbing (builder).

---

## 1. gdsfactory Fork — Provenance Injection

### 1.1 Call-stack capture

In `Component.write_gds()`, before serializing layout:

```python
import inspect
import os

_call_site_counter = {}
PROJECT_ROOT = os.getenv("GDS_PROJECT_ROOT", os.getcwd())

def _is_internal(filepath):
    """Skip gdsfactory own frames, stdlib, site-packages."""
    return any(pat in filepath.replace("\\", "/") for pat in [
        "/gdsfactory/", "/site-packages/", "<frozen", "<string>",
        "/importlib/", "/klayout/",
    ])

def _capture_provenance():
    for fi in inspect.stack():
        fp = fi.filename
        if _is_internal(fp):
            continue
        rel = os.path.relpath(fp, PROJECT_ROOT)
        key = (rel, fi.lineno, fi.function)
        _call_site_counter[key] = _call_site_counter.get(key, 0) + 1
        prov = {
            "file": rel,
            "function": fi.function,
            "line": fi.lineno,
            "call_index": _call_site_counter[key],
        }
        if "self" in fi.frame.f_locals:
            prov["class_name"] = type(fi.frame.f_locals["self"]).__name__
        return prov
    return {}
```

### 1.2 Write PROPATTR into GDS

```python
import klayout.db as kdb

def _write_provenance_to_cell(cell, provenance):
    props = kdb.Properties()
    for k, v in provenance.items():
        props.set(k, str(v))
    cell.set_properties(props)
```

Call `_capture_provenance()` then `_write_provenance_to_cell()` inside `Component.write_gds()`.

**Coverage:**

| Code pattern | Captured fields |
|-------------|----------------|
| `c = gf.c.mzi()` at module level | `file`, `function: <module>`, `line`, `call_index` |
| Called inside `def my_func()`  | `file`, `function: my_func`, `line`, `call_index` |
| Called inside `class Foo.build()` | `file`, `function: build`, `class_name: Foo`, `line`, `call_index` |
| Inside `for i in range(10):` | 10 cells, each with distinct `call_index: 1..10`, same `file/line/function` |

---

## 2. gds-parser — PROPATTR Extraction

### 2.1 Extract cell properties in `parse_gds()`

In `gds-services/parser/main.py`, after reading layout and iterating layers:

```python
def extract_provenance(layout, cell) -> dict:
    """Read PROPATTR from a cell and return provenance dict."""
    props = cell.property_list()
    if not props:
        return {}
    return {str(k): str(v) for k, v in props.items()}
```

### 2.2 Enriched GeoJSON Feature

Each feature's `properties`:

```python
{
    "layer": 1,
    "data_type": 0,
    "color": "#4ecdc4",
    "cell": top_cell_name,
    "provenance": {
        "file": "designs/mzi.py",
        "function": "mzi_te",
        "line": 42,
        "class_name": None,       # or "MZIBuilder"
        "call_index": 3
    },
    "area_um2": 6900.0,
    "vertex_count": 182,
    "bbox": [0.0, 0.0, 230.0, 30.0]
}
```

### 2.3 Coordinate metadata per polygon

```python
def polygon_metadata(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    # Shoelace area
    area = 0.5 * abs(sum(
        xs[i] * ys[i+1] - xs[i+1] * ys[i]
        for i in range(len(ring) - 1)
    ))
    return {
        "area_um2": round(area, 2),
        "vertex_count": len(ring) - 1,  # last = first
        "bbox": [min(xs), min(ys), max(xs), max(ys)],
    }
```

---

## 3. viewer.html — Click-to-Inspect + Console + YAML Export

### 3.1 Layout restructure

```
┌──────────┬──────────────────────────┐
│ #sidebar │      #map-container      │
│  220px   │  ┌────────────────────┐  │
│          │  │       #map         │  │
│  files   │  │                    │  │
│  legend  │  └────────────────────┘  │
│          │  ┌────────────────────┐  │
│          │  │     #console       │  │
│          │  │  collapsible       │  │
│          │  │  default 180px     │  │
│          │  └────────────────────┘  │
└──────────┴──────────────────────────┘
```

CSS: `#map-container { flex:1; display:flex; flex-direction:column; }`
`#map { flex:1; min-height:300px; }`
`#console { height:180px; background:#111; color:#cdd6f4; overflow-y:auto; padding:12px; font:13px monospace; border-top:2px solid #313244; flex-shrink:0; }`

Console header bar with: title ("Inspect"), collapse toggle, Copy YAML button.

### 3.2 Click interaction

```javascript
var selectInteraction = new ol.interaction.Select({
    layers: [vectorLayer],
    style: function(feature) {
        return new ol.style.Style({
            stroke: new ol.style.Stroke({ color: '#ffffff', width: 3 }),
            fill: new ol.style.Fill({ color: feature.get('color') + 'cc' })
        });
    }
});
map.addInteraction(selectInteraction);

selectInteraction.on('select', function(e) {
    if (e.selected.length > 0) {
        showInspectPanel(e.selected[0]);
    } else {
        clearInspectPanel();
    }
});
```

OpenLayers `ol.interaction.Select` handles click-to-select and click-empty-to-deselect natively.

### 3.3 Console panel content

```
┌─────────────────────────────────────────────┐
│ ▼ Inspect                        [📋 Copy] │
├─────────────────────────────────────────────┤
│ cell         mzi_te                        │
│ layer        1 / 0  (WG)                   │
│ file         designs/mzi.py:42             │
│ function     mzi_te()                      │
│ class        —                             │
│ call_index   3                             │
│ area         6900.00 µm²                   │
│ bbox         [0, 0, 230, 30]               │
│ vertices     182                           │
│ repo         RuihuanFang/phononic-superc.. │
│ ref          main                          │
│ path         build/gds/mzi.gds            │
└─────────────────────────────────────────────┘
```

### 3.4 YAML copy

```javascript
function copyYAML() {
    var data = getInspectData();  // from current selected feature
    var yaml = [
        "cell: " + data.cell,
        "layer: " + data.layer + "/" + data.data_type,
        "file: " + (data.provenance.file || "?") + ":" + (data.provenance.line || "?"),
        "function: " + (data.provenance.function || "?"),
        "class_name: " + (data.provenance.class_name || ""),
        "call_index: " + (data.provenance.call_index || ""),
        "area_um2: " + data.area_um2,
        "bbox: " + JSON.stringify(data.bbox),
        "vertex_count: " + data.vertex_count,
        "repo: " + repo,
        "ref: " + branch,
        "path: " + currentFilePath,
    ].join("\n");
    navigator.clipboard.writeText(yaml).then(function() {
        var btn = document.getElementById('copy-btn');
        btn.textContent = 'Copied ✓';
        setTimeout(function() { btn.textContent = '📋 Copy'; }, 2000);
    });
}
```

### 3.5 Collapsible console

Console header bar acts as toggle: click to collapse to 32px (header only), click to expand back to 180px. Default: expanded when a polygon is selected.

---

## 4. gds-builder — Isolated Build Pipeline

### 4.1 Build model — no clone

Repo bare data lives at `/data/git/repositories/<owner>/<repo>.git` (shared volume from Gitea). Builder uses `git` plumbing directly:

```python
import subprocess, tempfile, pathlib, shutil

BUILD_CACHE = pathlib.Path("/data/build-cache")

def build_design(repo, design_path, ref="main"):
    owner, name = repo.split("/")
    bare = REPOS_DIR / owner.lower() / f"{name.lower()}.git"
    
    # 1. Create temp workspace
    ws = tempfile.mkdtemp(prefix="gdsbuild-")
    try:
        # 2. Extract target file + its dependencies from bare repo
        #    git --git-dir show <ref>:<path> for each needed file
        _extract_files(bare, ref, [design_path], ws)
        
        # 3. Install forked gdsfactory in workspace venv
        subprocess.run(["pip", "install", "-e", "/gdsfactory-fork"], 
                       cwd=ws, check=True)
        
        # 4. Run the design script
        out = subprocess.run(
            ["python", str(ws / design_path)],
            cwd=ws, capture_output=True, text=True, timeout=300,
            env={**os.environ, "GDS_PROJECT_ROOT": str(ws)}
        )
        
        # 5. Collect produced .gds files
        gds_dir = ws / "build" / "gds"
        if gds_dir.exists():
            cache_dir = BUILD_CACHE / owner.lower() / name.lower() / ref
            cache_dir.mkdir(parents=True, exist_ok=True)
            for gds in gds_dir.glob("*.gds"):
                shutil.copy(gds, cache_dir / gds.name)
        
        return {"status": "ok", "output": out.stdout, "stderr": out.stderr}
    finally:
        shutil.rmtree(ws)
```

### 4.2 File extraction

```python
def _extract_files(bare_repo, ref, paths, workspace):
    """Checkout specific paths from bare repo into workspace."""
    for p in paths:
        result = subprocess.run(
            ["git", "--git-dir", str(bare_repo), "show", f"{ref}:{p}"],
            capture_output=True
        )
        if result.returncode == 0:
            target = pathlib.Path(workspace) / p
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(result.stdout)
```

No clone, no version tracking. Only the needed source files are materialized into a temp dir.

### 4.3 API endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /build?repo=O/R&design=designs/mzi.py&ref=main` | Build single design |
| `POST /build/all?repo=O/R&ref=main` | Discover `designs/` or `Snakefile` and build all |
| `GET /health` | Health check |

---

## 5. Data Flow Summary

```
User writes designs/mzi.py in gitea repo
          │
          ▼
  POST /build?design=designs/mzi.py
          │
          ▼
  gds-builder: extract file from bare git → run forked gdsfactory
          │
          ▼
  gdsfactory: _capture_provenance() via inspect.stack()
          │
          ▼
  write_gds() with PROPATTR per cell  ──→  build/gds/mzi.gds
                                                 │
                                                 ▼
  User clicks GDS tab in Gitea  ──→  viewer.html loads /data?path=build/gds/mzi.gds
                                                 │
                                                 ▼
  gds-parser: parse_gds() reads PROPATTR  ──→  GeoJSON with provenance
                                                 │
                                                 ▼
  viewer: OpenLayers renders polygons
          User clicks a polygon  ──→  highlight + console panel
          [📋 Copy]  ──→  YAML in clipboard → paste into issue
```

---

## 6. Rebuild Cost

| Component | Changed files | Rebuild time |
|-----------|-------------|-------------|
| viewer UI | `viewer.html` only | ~7s |
| parser | `main.py` | ~10s |
| builder | `builder/main.py` | ~10s |
| gdsfactory fork | requires rebuild of builder image + phononic-superconductor build | ~30s |
| Gitea | **not changed** | 0 |

---

## 7. Error Handling

- **Missing PROPATTR** (old GDS without provenance): console shows "no provenance data" for those fields, YAML omits them
- **Multiple cells in one GDS**: provenance attached to each cell individually, polygon click reveals the right cell's provenance
- **Build timeout**: 300s hard limit, returns `{"status": "timeout"}`
- **Extract failure**: if `git show` fails (file deleted in this ref), return 404 for that file
