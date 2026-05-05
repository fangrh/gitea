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
            key = (info.layer, info.datatype)
            if key not in layers:
                layers[key] = []
            region = kdb.Region(it)
            region.merge()
            for poly in region.each():
                pts = poly.to_simple_polygon()
                ring = [[p.x * layout.dbu, p.y * layout.dbu] for p in pts.each_point()]
                if len(ring) >= 3:
                    ring.append(ring[0])
                    layers[key].append([ring])

    features = []
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for key, polys in layers.items():
        if not polys:
            continue
        color = LAYER_COLORS[key[0] % len(LAYER_COLORS)]
        features.append({
            "type": "Feature",
            "geometry": {"type": "MultiPolygon", "coordinates": polys},
            "properties": {"layer": key[0], "data_type": key[1], "color": color},
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
