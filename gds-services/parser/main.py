"""GDS Parser Service — parses .gds files into GeoJSON using klayout."""
import io
import json
import pathlib
import subprocess
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import Response, FileResponse

app = FastAPI(title="gds-parser")
BUILD_CACHE = pathlib.Path("/data/build-cache")

LAYER_COLORS = [
    "#4ecdc4", "#ff6b6b", "#45b7d1", "#96ceb4",
    "#ffeaa7", "#dfe6e9", "#fd79a8", "#a29bfe",
    "#6c5ce7", "#00b894", "#e17055", "#0984e3",
    "#fab1a0", "#81ecec", "#55efc4", "#74b9ff",
]


PROVENANCE_LAYER = (255, 255)


def _extract_provenance(layout) -> dict[str, dict]:
    """Return ``{cell_name: provenance_dict}`` from TEXT on layer 255/255."""
    import json as _json
    import klayout.db as kdb

    prov = {}
    prov_li = layout.layer(*PROVENANCE_LAYER)
    if prov_li is None:
        return prov
    for ci in range(layout.cells()):
        cell = layout.cell(ci)
        for shape in cell.shapes(prov_li).each(kdb.Shapes.STexts):
            try:
                entry = _json.loads(shape.text.string)
                name = entry.get("cell") or cell.name or ""
                if name:
                    prov[name] = entry
            except Exception:
                pass
    return prov


def _polygon_metadata(ring):
    """Return area_um2, vertex_count, bbox for a ring."""
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    area = 0.5 * abs(sum(
        xs[i] * ys[i + 1] - xs[i + 1] * ys[i]
        for i in range(len(ring) - 1)
    ))
    return {
        "area_um2": round(area, 4),
        "vertex_count": len(ring) - 1,  # last == first
        "bbox": [round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6)],
    }


def parse_gds(data: bytes) -> dict:
    """Parse GDSII binary and return GeoJSON FeatureCollection."""
    import tempfile, os
    import klayout.db as kdb
    tmp = tempfile.NamedTemporaryFile(suffix=".gds", delete=False)
    try:
        tmp.write(data)
        tmp.close()
        layout = kdb.Layout()
        layout.read(tmp.name)
    finally:
        os.unlink(tmp.name)

    provenance_by_cell = _extract_provenance(layout)

    layers = {}
    top = layout.top_cell()
    for li in layout.layer_indexes():
        info = layout.layer_infos()[li]
        if (info.layer, info.datatype) == PROVENANCE_LAYER:
            continue
        it = top.begin_shapes_rec(li)
        if it.at_end():
            continue
        key = (info.layer, info.datatype)
        if key not in layers:
            layers[key] = {"polys": [], "provenance_by_cell": {}}
        region = kdb.Region(it)
        region.merge()
        for poly in region.each():
            pts = poly.to_simple_polygon()
            ring = [[p.x * 0.001, p.y * 0.001] for p in pts.each_point()]
            if len(ring) >= 3:
                ring.append(ring[0])
                layers[key]["polys"].append([ring])

    # Find which cells contribute to which layers
    for ci in range(layout.cells()):
        cell = layout.cell(ci)
        if not cell.name:
            continue
        cell_prov = provenance_by_cell.get(cell.name)
        for li in layout.layer_indexes():
            linfo = layout.layer_infos()[li]
            if (linfo.layer, linfo.datatype) == PROVENANCE_LAYER:
                continue
            if cell.shapes(li).is_empty():
                continue
            key = (linfo.layer, linfo.datatype)
            if key in layers and cell_prov:
                layers[key]["provenance_by_cell"][cell.name] = cell_prov

    features = []
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for key, entry in layers.items():
        polys = entry["polys"]
        if not polys:
            continue
        color = LAYER_COLORS[key[0] % len(LAYER_COLORS)]
        properties = {"layer": key[0], "data_type": key[1], "color": color}
        if entry["provenance_by_cell"]:
            properties["provenance_by_cell"] = entry["provenance_by_cell"]
        features.append({
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": polys},
            "properties": properties,
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


@app.get("/viewer")
def viewer():
    return FileResponse("viewer.html", media_type="text/html")


def _has_provenance(gds_path: pathlib.Path) -> bool:
    """Quick check if a GDS file has provenance TEXT on layer 255/255."""
    try:
        import klayout.db as kdb
        layout = kdb.Layout()
        layout.read(str(gds_path))
        prov_li = layout.layer(255, 255)
        if prov_li is None:
            return False
        for ci in range(layout.cells()):
            if not layout.cell(ci).shapes(prov_li).is_empty():
                return True
        return False
    except Exception:
        return False


@app.get("/files")
def list_files(repo: str, ref: str = "main"):
    owner, name = repo.split("/")
    repo_dir = pathlib.Path(f"/data/git/repositories/{owner.lower()}/{name.lower()}.git")
    entries = []  # list of {name, has_provenance}
    seen = set()

    # From git
    if repo_dir.exists():
        result = subprocess.run(
            ["git", "--git-dir", str(repo_dir), "ls-tree", "-r", "--name-only", ref],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            for f in result.stdout.splitlines():
                f = f.strip()
                if f.endswith(".gds"):
                    # Check if cache version exists (and has provenance)
                    cache_file = BUILD_CACHE / owner.lower() / name.lower() / ref / f
                    has_prov = _has_provenance(cache_file) if cache_file.exists() else False
                    entries.append({"name": f, "has_provenance": has_prov})
                    seen.add(f)

    # From build cache (files not in git)
    cache_dir = BUILD_CACHE / owner.lower() / name.lower() / ref
    if cache_dir.exists():
        for gds in cache_dir.rglob("*.gds"):
            rel = str(gds.relative_to(cache_dir)).replace("\\", "/")
            if rel not in seen:
                has_prov = _has_provenance(gds)
                entries.append({"name": rel, "has_provenance": has_prov})
                seen.add(rel)

    return entries


@app.get("/data")
def get_gds_data(repo: str, ref: str = "main", path: str = ""):
    owner, name = repo.split("/")
    repo_dir = pathlib.Path(f"/data/git/repositories/{owner.lower()}/{name.lower()}.git")

    # Try build cache first
    cache_file = BUILD_CACHE / owner.lower() / name.lower() / ref / path
    if cache_file.exists():
        return Response(
            content=json.dumps(parse_gds(cache_file.read_bytes())),
            media_type="application/json",
        )

    # Fall back to git
    if not repo_dir.exists():
        raise HTTPException(404, f"Repo not found: {repo}")
    result = subprocess.run(
        ["git", "--git-dir", str(repo_dir), "show", f"{ref}:{path}"],
        capture_output=True,
    )
    if result.returncode != 0:
        raise HTTPException(404, f"File not found: {path}")
    return Response(content=json.dumps(parse_gds(result.stdout)), media_type="application/json")


@app.get("/source")
def get_source(repo: str, ref: str = "main", path: str = ""):
    """Return source file content for code inspection."""
    owner, name = repo.split("/")
    repo_dir = pathlib.Path(f"/data/git/repositories/{owner.lower()}/{name.lower()}.git")
    if not repo_dir.exists():
        raise HTTPException(404, f"Repo not found: {repo}")
    result = subprocess.run(
        ["git", "--git-dir", str(repo_dir), "show", f"{ref}:{path}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise HTTPException(404, f"File not found: {path}")
    return Response(content=result.stdout, media_type="text/plain; charset=utf-8")
