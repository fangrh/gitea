# Drawing Toolbar for GDS Viewer

**Date:** 2026-05-06
**Status:** Draft
**Scope:** `gds-services/parser/viewer.html` (single file change)

## Problem

Users need to annotate areas on the GDS canvas when filing issues. Currently they can only select existing GDS polygons. They need to draw basic geometric shapes to mark regions, then copy the shape's geometry as YAML to paste into issue descriptions.

## Design

### UI Layout

Right-side vertical toolbar (40px wide, `#1e1e2e` background), between the map canvas and console panel.

| Button | Function | Icon |
|--------|----------|------|
| Select | Switch to select mode (default) | Arrow pointer |
| Rectangle | Draw rectangle | Box |
| Circle | Draw circle | Circle |
| Line | Draw line segment | Diagonal line |
| Polygon | Draw polygon | Pentagon |
| Delete | Delete selected drawn shapes | X |
| Snap | Toggle snap on/off | Magnet |

- Active button highlighted with `#89b4fa` background
- Tooltips in English (title attribute)

### Mode Switching

- Click draw button -> disable Select/DragBox, activate corresponding Draw interaction
- Drawing completes (single draw action) -> auto-switch back to select mode
- Click select button -> disable all Draw interactions, activate Select/DragBox
- Escape during drawing -> cancel current draw, switch to select mode

### Data Layer

Independent from GDS data:

- `drawSource = new ol.source.Vector()` — stores user-drawn shapes
- `drawLayer = new ol.layer.Vector({ source: drawSource })` — separate layer above vectorLayer
- Each drawn feature has properties: `{ isDrawn: true, shapeType: 'rectangle'|'circle'|'line'|'polygon' }`

Drawn shapes persist when switching GDS files (not cleared by `loadGDS`).

### Drawing Shape Styles

Distinct from GDS polygons:

- Default: dashed stroke `#f38ba8` (red), width 2, `lineDash: [8, 4]`, fill `rgba(243, 139, 168, 0.1)`
- Selected: white solid stroke, fill `rgba(243, 139, 168, 0.3)`

### Drawing Interactions

Using OpenLayers built-in interactions:

- `ol.interaction.Draw` — one instance per shape type (rectangle, circle, line, polygon)
- `ol.interaction.Modify` — activated when a drawn shape is selected, allows vertex dragging
- `ol.interaction.Translate` — activated alongside Modify, allows whole-shape dragging

Only active for features with `isDrawn: true`. GDS polygons are not modifiable.

### Snapping

Toggle via Snap button in toolbar. When active:

1. **Grid snap** — snap to grid intersection points at current zoom level (resolution-based integer grid: 1um at fine zoom, 10um at coarse zoom)
2. **Feature snap** — snap to vertices and edges of GDS polygons (`vectorLayer` source) and drawn shapes (`drawSource`)

Implementation: two `ol.interaction.Snap` instances with 10px pixel tolerance. Grid snap source updated on zoom/pan.

### Selection Coordination

- Select interaction covers both `vectorLayer` and `drawLayer`
- `onSelectionChanged` checks `isDrawn` property to route to appropriate display:
  - GDS polygon -> existing provenance-based info panel
  - Drawn shape -> shape property display (type, coordinates, dimensions)
- Delete key only removes features with `isDrawn: true`

### Shape Info Panel

When a drawn shape is selected, Info panel shows:
- `type`: rectangle / circle / line / polygon
- `coordinates`: vertex coordinates
- `bbox`: bounding box `[xmin, ymin, xmax, ymax]`
- Shape-specific fields (width/height, radius, length, area, center)

No provenance data for drawn shapes.

### YAML Output

**Single drawn shape:**

Rectangle:
```yaml
shape: rectangle
coordinates: [[100.0, 200.0], [150.0, 200.0], [150.0, 230.0], [100.0, 230.0]]
bbox: [100.0, 200.0, 150.0, 230.0]
width: 50.0
height: 30.0
center: [125.0, 215.0]
```

Circle:
```yaml
shape: circle
center: [125.0, 215.0]
radius: 25.0
bbox: [100.0, 190.0, 150.0, 240.0]
```

Line:
```yaml
shape: line
coordinates: [[100.0, 200.0], [150.0, 230.0]]
length: 58.31
```

Polygon:
```yaml
shape: polygon
coordinates: [[100.0, 200.0], [150.0, 200.0], [160.0, 230.0], [100.0, 230.0]]
bbox: [100.0, 200.0, 160.0, 230.0]
area: 1800.0
center: [127.5, 215.0]
```

**Multiple drawn shapes selected:**
```yaml
annotations:
  - shape: rectangle
    bbox: [100.0, 200.0, 150.0, 230.0]
    width: 50.0
    height: 30.0
  - shape: circle
    center: [125.0, 215.0]
    radius: 25.0
```

**Mixed selection (GDS polygons + drawn shapes):**
```yaml
modifications:
  - file: ring.py
    lines: [12]
annotations:
  - shape: rectangle
    bbox: [100.0, 200.0, 150.0, 230.0]
    width: 50.0
    height: 30.0
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Delete` / `Backspace` | Delete selected drawn shapes |
| `Escape` | Clear selection / cancel draw / switch to select mode |
| `1` | Select mode |
| `2` | Rectangle draw mode |
| `3` | Circle draw mode |
| `4` | Line draw mode |
| `5` | Polygon draw mode |
| `S` | Toggle snap |

### Edge Cases

- Drawing mode: Select/DragBox disabled, cannot select GDS polygons
- Select mode: Draw interactions disabled
- Polygon drawing: double-click or click starting point to complete
- Circle drawing: drag to define center + radius
- Modify/Translate only active for selected drawn shapes
- GDS file switch preserves drawn shapes
- All coordinates in um (consistent with GDS)

## File Impact

Only `gds-services/parser/viewer.html` is modified. No backend changes required.
