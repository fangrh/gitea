# Drawing Toolbar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a right-side drawing toolbar to the GDS viewer with shape drawing (rectangle, circle, line, polygon), editing (move, resize), snapping, shape info display, and YAML export.

**Architecture:** Independent `drawLayer` on top of the existing GDS `vectorLayer`. OpenLayers `Draw`, `Modify`, `Translate`, and `Snap` interactions are activated/deactivated based on the current mode (select vs draw). The existing Select/DragBox interactions are extended to cover both layers.

**Tech Stack:** OpenLayers 10, vanilla JavaScript

---

### Task 1: HTML structure, CSS, drawLayer, and mode state

**Files:**
- Modify: `gds-services/parser/viewer.html` (CSS + HTML + JS)

- [ ] **Step 1: Add CSS for toolbar and drawn shapes**

Add before `</style>` (after the `.file-section-body.open` rule):

```css
/* Drawing toolbar */
#map-row { display: flex; flex: 1; min-height: 0; }
#draw-toolbar { width: 40px; background: #1e1e2e; border-left: 1px solid #313244; display: flex; flex-direction: column; align-items: center; padding: 8px 0; gap: 4px; flex-shrink: 0; }
.tool-btn { width: 32px; height: 32px; background: transparent; border: 1px solid transparent; border-radius: 4px; cursor: pointer; display: flex; align-items: center; justify-content: center; color: #6c7086; padding: 0; }
.tool-btn:hover { background: #313244; color: #cdd6f4; }
.tool-btn.active { background: #45475a; color: #89b4fa; border-color: #89b4fa; }
.tool-btn svg { width: 18px; height: 18px; stroke: currentColor; fill: none; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.tool-btn svg.filled { fill: currentColor; }
```

- [ ] **Step 2: Modify HTML to wrap map + toolbar**

Replace the `<div id="map"></div>` line (line 64) with:

```html
<div id="map-row">
    <div id="map" style="flex:1;"></div>
    <div id="draw-toolbar">
        <button class="tool-btn active" data-mode="select" title="Select (1)" onclick="setMode('select')">
            <svg viewBox="0 0 24 24"><path d="M5 3l14 9-7 2-3 7z"/></svg>
        </button>
        <button class="tool-btn" data-mode="rectangle" title="Rectangle (2)" onclick="setMode('rectangle')">
            <svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="1"/></svg>
        </button>
        <button class="tool-btn" data-mode="circle" title="Circle (3)" onclick="setMode('circle')">
            <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/></svg>
        </button>
        <button class="tool-btn" data-mode="line" title="Line (4)" onclick="setMode('line')">
            <svg viewBox="0 0 24 24"><line x1="5" y1="19" x2="19" y2="5"/></svg>
        </button>
        <button class="tool-btn" data-mode="polygon" title="Polygon (5)" onclick="setMode('polygon')">
            <svg viewBox="0 0 24 24"><path d="M12 3l9 7-3 10H6L3 10z"/></svg>
        </button>
        <div style="height:1px;width:24px;background:#313244;margin:4px 0;"></div>
        <button class="tool-btn" data-mode="delete" title="Delete drawn" onclick="deleteDrawn()">
            <svg viewBox="0 0 24 24"><line x1="6" y1="6" x2="18" y2="18"/><line x1="18" y1="6" x2="6" y2="18"/></svg>
        </button>
        <button class="tool-btn" data-mode="snap" title="Snap (S)" onclick="toggleSnap()">
            <svg viewBox="0 0 24 24"><path d="M6 16c0-3.3 2.7-6 6-6s6 2.7 6 6v3H6z"/><line x1="12" y1="3" x2="12" y2="7"/></svg>
        </button>
    </div>
</div>
```

Remove the old `#map { flex: 1; min-height: 300px; }` CSS rule (it's now set inline via `style="flex:1;"`).

- [ ] **Step 3: Add drawLayer and state variables**

In the JS section, after `var expandedFiles = {};` (line ~92) add:

```javascript
var currentMode = 'select';
var snapActive = false;
var drawInteractions = {};

var drawSource = new ol.source.Vector();

var drawStyleDefault = new ol.style.Style({
    stroke: new ol.style.Stroke({ color: '#f38ba8', width: 2, lineDash: [8, 4] }),
    fill: new ol.style.Fill({ color: 'rgba(243, 139, 168, 0.1)' })
});

var drawStyleSelected = new ol.style.Style({
    stroke: new ol.style.Stroke({ color: '#ffffff', width: 3 }),
    fill: new ol.style.Fill({ color: 'rgba(243, 139, 168, 0.3)' })
});

var drawLayer = new ol.layer.Vector({
    source: drawSource,
    style: function(feature) {
        return feature.get('selected') ? drawStyleSelected : drawStyleDefault;
    }
});
```

Then in the `map` initialization (find `layers: [vectorLayer]`), change to:

```javascript
layers: [vectorLayer, drawLayer],
```

- [ ] **Step 4: Add setMode function**

Add after the `clearSelection` function:

```javascript
function setMode(mode) {
    if (mode === currentMode && mode !== 'select') {
        mode = 'select'; // toggle off -> back to select
    }
    currentMode = mode;

    // Deactivate all draw interactions
    Object.keys(drawInteractions).forEach(function(key) {
        drawInteractions[key].setActive(false);
    });

    var isDrawMode = (mode !== 'select');
    selectClick.setActive(!isDrawMode);
    dragBox.setActive(!isDrawMode);

    if (isDrawMode && drawInteractions[mode]) {
        drawInteractions[mode].setActive(true);
    }

    // Update toolbar buttons (snap and delete are separate toggles)
    document.querySelectorAll('.tool-btn[data-mode]').forEach(function(btn) {
        if (btn.dataset.mode === 'snap' || btn.dataset.mode === 'delete') return;
        btn.classList.toggle('active', btn.dataset.mode === mode);
    });
}
```

- [ ] **Step 5: Update Escape handler**

In the existing keydown listener, replace the `if (e.key === 'Escape') clearSelection();` line with:

```javascript
if (e.key === 'Escape') {
    if (currentMode !== 'select') {
        setMode('select');
    }
    clearSelection();
}
```

- [ ] **Step 6: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): add drawing toolbar HTML, CSS, drawLayer, and mode state"
```

---

### Task 2: Draw interactions (4 shape types)

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Add Draw interactions after dragBox handler**

Add after the `dragBox.on('boxend', ...)` closing `});` (after line ~416):

```javascript
// --- Draw interactions ---
var drawRectangle = new ol.interaction.Draw({
    source: drawSource,
    type: 'Circle',
    geometryFunction: ol.interaction.Draw.createBox()
});
drawRectangle.setActive(false);
map.addInteraction(drawRectangle);
drawInteractions['rectangle'] = drawRectangle;

var drawCircle = new ol.interaction.Draw({
    source: drawSource,
    type: 'Circle'
});
drawCircle.setActive(false);
map.addInteraction(drawCircle);
drawInteractions['circle'] = drawCircle;

var drawLine = new ol.interaction.Draw({
    source: drawSource,
    type: 'LineString'
});
drawLine.setActive(false);
map.addInteraction(drawLine);
drawInteractions['line'] = drawLine;

var drawPolygon = new ol.interaction.Draw({
    source: drawSource,
    type: 'Polygon'
});
drawPolygon.setActive(false);
map.addInteraction(drawPolygon);
drawInteractions['polygon'] = drawPolygon;
```

- [ ] **Step 2: Add drawend handler for all draw interactions**

Add after the draw interactions:

```javascript
Object.keys(drawInteractions).forEach(function(key) {
    drawInteractions[key].on('drawend', function(e) {
        var feature = e.feature;
        feature.set('isDrawn', true);
        feature.set('shapeType', key);
        feature.set('selected', false);
        // Auto-switch back to select mode after drawing
        setTimeout(function() { setMode('select'); }, 50);
    });
});
```

- [ ] **Step 3: Verify drawing works**

Open viewer, click Rectangle button on right toolbar, drag on map. A red dashed rectangle should appear. After drawing, toolbar switches back to Select mode. Repeat for Circle, Line, Polygon.

- [ ] **Step 4: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): add Draw interactions for rectangle, circle, line, polygon"
```

---

### Task 3: Select drawn shapes and update Select interaction

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Update Select interaction to cover both layers**

Find the `selectClick` initialization and change `layers: [vectorLayer]` to `layers: [vectorLayer, drawLayer]`:

```javascript
var selectClick = new ol.interaction.Select({
    layers: [vectorLayer, drawLayer],
    style: null,
    multi: true
});
```

- [ ] **Step 2: Update selectClick handler to handle drawn shapes**

Replace the existing `selectClick.on('select', function(e) { ... });` with:

```javascript
selectClick.on('select', function(e) {
    var clicked = e.selected.length > 0 ? e.selected[0] : null;

    if (clicked) {
        var alreadySelected = selectedFeatures.getArray().includes(clicked);
        if (ctrlPressed) {
            if (alreadySelected) {
                removeFromSelection([clicked]);
            } else {
                addToSelection([clicked]);
            }
        } else {
            replaceSelection([clicked]);
        }
    } else {
        clearSelection();
        return;
    }

    selectClick.getFeatures().clear();
    vectorLayer.changed();
    drawLayer.changed();
    onSelectionChanged();
});
```

- [ ] **Step 3: Update DragBox handler to include drawn features**

In the existing DragBox `boxend` handler, replace the feature collection loop to check both layers:

```javascript
dragBox.on('boxend', function(e) {
    var extent = dragBox.getGeometry().getExtent();
    var dragDist = Math.sqrt(
        Math.pow(e.pixel[0] - dragStartPixel[0], 2) +
        Math.pow(e.pixel[1] - dragStartPixel[1], 2)
    );

    if (dragDist < 5) return;

    var featuresInBox = [];
    source.forEachFeatureInExtent(extent, function(f) {
        if (f.get('visible') !== false) {
            var geom = f.getGeometry();
            if (geom && ol.extent.intersects(extent, geom.getExtent())) {
                featuresInBox.push(f);
            }
        }
    });
    drawSource.forEachFeatureInExtent(extent, function(f) {
        var geom = f.getGeometry();
        if (geom && ol.extent.intersects(extent, geom.getExtent())) {
            featuresInBox.push(f);
        }
    });

    if (ctrlPressed) {
        addToSelection(featuresInBox);
    } else {
        replaceSelection(featuresInBox);
    }

    vectorLayer.changed();
    drawLayer.changed();
    onSelectionChanged();
});
```

- [ ] **Step 4: Update clearSelection to also refresh drawLayer**

Replace the existing `clearSelection` function:

```javascript
function clearSelection() {
    selectedFeatures.forEach(function(f) { f.set('selected', false); });
    selectedFeatures.clear();
    vectorLayer.changed();
    drawLayer.changed();
    onSelectionChanged();
}
```

- [ ] **Step 5: Verify selecting drawn shapes works**

Draw a shape, switch to Select mode, click it. It should highlight with white stroke. Click a GDS polygon — drawn shape deselects. Ctrl+click both — both selected.

- [ ] **Step 6: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): extend Select and DragBox to cover drawn shapes"
```

---

### Task 4: Modify and Translate interactions

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Add Modify and Translate interactions**

Add after the draw interactions block (after `drawInteractions['polygon'] = drawPolygon;`):

```javascript
// Modify interaction for drawn shape vertices
var modifyInteraction = new ol.interaction.Modify({
    source: drawSource,
    style: new ol.style.Style({
        image: new ol.style.Circle({
            radius: 5,
            fill: new ol.style.Fill({ color: '#f38ba8' }),
            stroke: new ol.style.Stroke({ color: '#ffffff', width: 1 })
        })
    })
});
modifyInteraction.setActive(false);
map.addInteraction(modifyInteraction);

// Translate interaction for moving drawn shapes
var translateInteraction = new ol.interaction.Translate({
    layers: [drawLayer]
});
translateInteraction.setActive(false);
map.addInteraction(translateInteraction);
```

- [ ] **Step 2: Update onSelectionChanged to activate/deactivate Modify/Translate**

Replace the existing `onSelectionChanged` function:

```javascript
function onSelectionChanged() {
    var features = selectedFeatures.getArray();
    var count = features.length;

    // Activate Modify/Translate only when drawn shapes are selected
    var hasDrawn = count > 0 && features.some(function(f) { return f.get('isDrawn'); });
    modifyInteraction.setActive(hasDrawn);
    translateInteraction.setActive(hasDrawn);

    if (count === 0) {
        clearInspect();
        return;
    }

    var drawnFeatures = features.filter(function(f) { return f.get('isDrawn'); });
    var gdsFeatures = features.filter(function(f) { return !f.get('isDrawn'); });

    if (drawnFeatures.length > 0 && gdsFeatures.length === 0) {
        if (drawnFeatures.length === 1) {
            showDrawnInspect(drawnFeatures[0]);
        } else {
            showDrawnMultiInspect(drawnFeatures);
        }
    } else if (drawnFeatures.length === 0) {
        if (gdsFeatures.length === 1) {
            showInspect(gdsFeatures[0]);
        } else {
            showMultiInspect(gdsFeatures);
        }
    } else {
        showMixedInspect(gdsFeatures, drawnFeatures);
    }
}
```

- [ ] **Step 3: Verify Modify and Translate work**

Draw a rectangle, select it. Drag a vertex — shape should resize. Drag the body — shape should move.

- [ ] **Step 4: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): add Modify and Translate interactions for drawn shapes"
```

---

### Task 5: Shape info panel display

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Add shape geometry helper functions**

Add after the `esc` function (after line ~601):

```javascript
function getShapeGeom(feature) {
    var type = feature.get('shapeType');
    var geom = feature.getGeometry();
    var result = { type: type };

    if (type === 'rectangle' || type === 'polygon') {
        var coords = geom.getCoordinates()[0];
        // Remove closing point (last = first)
        result.coordinates = coords.slice(0, -1).map(function(c) { return [Math.round(c[0] * 100) / 100, Math.round(c[1] * 100) / 100]; });
        var ext = geom.getExtent();
        result.bbox = [Math.round(ext[0] * 100) / 100, Math.round(ext[1] * 100) / 100, Math.round(ext[2] * 100) / 100, Math.round(ext[3] * 100) / 100];
        result.width = Math.round((ext[2] - ext[0]) * 100) / 100;
        result.height = Math.round((ext[3] - ext[1]) * 100) / 100;
        result.center = [Math.round((ext[0] + ext[2]) / 2 * 100) / 100, Math.round((ext[1] + ext[3]) / 2 * 100) / 100];
        // Area via shoelace
        var area = 0;
        for (var i = 0; i < coords.length - 1; i++) {
            area += coords[i][0] * coords[i + 1][1] - coords[i + 1][0] * coords[i][1];
        }
        result.area = Math.round(Math.abs(area) / 2 * 100) / 100;
    } else if (type === 'circle') {
        var center = geom.getCenter();
        var radius = geom.getRadius();
        result.center = [Math.round(center[0] * 100) / 100, Math.round(center[1] * 100) / 100];
        result.radius = Math.round(radius * 100) / 100;
        result.bbox = [
            Math.round((center[0] - radius) * 100) / 100,
            Math.round((center[1] - radius) * 100) / 100,
            Math.round((center[0] + radius) * 100) / 100,
            Math.round((center[1] + radius) * 100) / 100
        ];
    } else if (type === 'line') {
        var coords = geom.getCoordinates();
        result.coordinates = coords.map(function(c) { return [Math.round(c[0] * 100) / 100, Math.round(c[1] * 100) / 100]; });
        var len = 0;
        for (var i = 1; i < coords.length; i++) {
            var dx = coords[i][0] - coords[i - 1][0];
            var dy = coords[i][1] - coords[i - 1][1];
            len += Math.sqrt(dx * dx + dy * dy);
        }
        result.length = Math.round(len * 100) / 100;
    }

    return result;
}
```

- [ ] **Step 2: Add showDrawnInspect function**

Add after `getShapeGeom`:

```javascript
function showDrawnInspect(feature) {
    var panel = document.getElementById('info-panel');
    panel.innerHTML = '';

    var sg = getShapeGeom(feature);
    var d = frag();
    addKV(d, 'type', sg.type, true);
    if (sg.coordinates) addKV(d, 'coordinates', JSON.stringify(sg.coordinates));
    if (sg.bbox) addKV(d, 'bbox', JSON.stringify(sg.bbox));
    if (sg.width !== undefined) addKV(d, 'width', sg.width + ' um');
    if (sg.height !== undefined) addKV(d, 'height', sg.height + ' um');
    if (sg.radius !== undefined) addKV(d, 'radius', sg.radius + ' um');
    if (sg.length !== undefined) addKV(d, 'length', sg.length + ' um');
    if (sg.area !== undefined) addKV(d, 'area', sg.area + ' um2');
    if (sg.center) addKV(d, 'center', JSON.stringify(sg.center));
    panel.appendChild(d);

    // Source panel: no source for drawn shapes
    document.getElementById('source-panel').innerHTML = '<p class="placeholder">Drawn shape — no source code</p>';
}
```

- [ ] **Step 3: Add showDrawnMultiInspect function**

```javascript
function showDrawnMultiInspect(features) {
    var panel = document.getElementById('info-panel');
    panel.innerHTML = '';

    addKV(panel, 'selected', 'Selected: ' + features.length + ' drawn shapes');

    features.forEach(function(f, idx) {
        addSep(panel);
        var sg = getShapeGeom(f);
        addKV(panel, 'shape ' + (idx + 1), sg.type, true);
        if (sg.bbox) addKV(panel, 'bbox', JSON.stringify(sg.bbox));
        if (sg.width !== undefined) addKV(panel, 'size', sg.width + ' x ' + sg.height + ' um');
        if (sg.radius !== undefined) addKV(panel, 'radius', sg.radius + ' um');
        if (sg.length !== undefined) addKV(panel, 'length', sg.length + ' um');
        if (sg.area !== undefined) addKV(panel, 'area', sg.area + ' um2');
    });

    document.getElementById('source-panel').innerHTML = '<p class="placeholder">Drawn shapes — no source code</p>';
}
```

- [ ] **Step 4: Add showMixedInspect function**

```javascript
function showMixedInspect(gdsFeatures, drawnFeatures) {
    var panel = document.getElementById('info-panel');
    panel.innerHTML = '';

    addKV(panel, 'selected', gdsFeatures.length + ' GDS + ' + drawnFeatures.length + ' drawn');

    if (gdsFeatures.length > 0) {
        addSep(panel);
        addKV(panel, 'GDS', gdsFeatures.length + ' polygon(s)');
    }
    if (drawnFeatures.length > 0) {
        addSep(panel);
        addKV(panel, 'Drawn', drawnFeatures.length + ' shape(s)');
        drawnFeatures.forEach(function(f, idx) {
            var sg = getShapeGeom(f);
            addKV(panel, '', sg.type + ' — ' + (sg.bbox ? JSON.stringify(sg.bbox) : ''));
        });
    }

    document.getElementById('source-panel').innerHTML = '<p class="placeholder">Mixed selection — see Info tab</p>';
}
```

- [ ] **Step 5: Verify shape info panel**

Draw a rectangle, select it. Info panel should show type, coordinates, bbox, width, height, center. Draw a circle, select it. Should show type, center, radius, bbox.

- [ ] **Step 6: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): shape info panel for drawn shapes"
```

---

### Task 6: YAML output for drawn shapes

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Add shapeToYAML helper**

Add after `showMixedInspect`:

```javascript
function shapeToYAML(sg) {
    var lines = [];
    lines.push('shape: ' + sg.type);
    if (sg.coordinates) lines.push('coordinates: ' + JSON.stringify(sg.coordinates));
    if (sg.bbox) lines.push('bbox: ' + JSON.stringify(sg.bbox));
    if (sg.width !== undefined) lines.push('width: ' + sg.width);
    if (sg.height !== undefined) lines.push('height: ' + sg.height);
    if (sg.center) lines.push('center: ' + JSON.stringify(sg.center));
    if (sg.radius !== undefined) lines.push('radius: ' + sg.radius);
    if (sg.length !== undefined) lines.push('length: ' + sg.length);
    if (sg.area !== undefined) lines.push('area: ' + sg.area);
    return lines;
}
```

- [ ] **Step 2: Replace copyYAML function**

Replace the entire existing `copyYAML` function with:

```javascript
function copyYAML(e) {
    e.stopPropagation();
    var features = selectedFeatures.getArray();
    if (features.length === 0) return;

    var drawnFeatures = features.filter(function(f) { return f.get('isDrawn'); });
    var gdsFeatures = features.filter(function(f) { return !f.get('isDrawn'); });

    var lines = [];

    // GDS modifications section
    if (gdsFeatures.length > 0) {
        if (gdsFeatures.length === 1 && drawnFeatures.length === 0) {
            // Single GDS — original format
            var f = gdsFeatures[0];
            var layer = f.get('layer') || '?';
            var provenance = f.get('provenance') || {};
            var meta = f.get('meta') || {};
            var bbox = (meta.bbox || []).map(function(v) { return v.toFixed(4); });

            lines = [
                'layer: ' + layer,
                'area_um2: ' + (meta.area_um2 || ''),
                'bbox: [' + bbox.join(', ') + ']',
                'vertex_count: ' + (meta.vertex_count || ''),
                'repo: ' + repo,
                'ref: ' + branch,
                'path: ' + currentFilePath
            ];
            if (Object.keys(provenance).length > 0) {
                lines.push('');
                if (provenance.instance_name) lines.push('instance_name: ' + provenance.instance_name);
                if (provenance.cell) lines.push('cell: ' + provenance.cell);
                if (provenance.file) lines.push('file: ' + provenance.file);
                if (provenance.line) lines.push('line: ' + provenance.line);
                if (provenance.function && provenance.function !== '<module>') lines.push('function: ' + provenance.function);
                if (provenance.class_name) lines.push('class_name: ' + provenance.class_name);
                if (provenance.call_index) lines.push('call_index: ' + provenance.call_index);
            }
        } else {
            // Multiple GDS — file-aggregated format
            var fileMap = {};
            gdsFeatures.forEach(function(f) {
                var prov = f.get('provenance') || {};
                if (prov.file && prov.line) {
                    var fp = prov.file.replace(/\\/g, '/');
                    if (!fileMap[fp]) fileMap[fp] = [];
                    var ln = parseInt(prov.line);
                    if (fileMap[fp].indexOf(ln) === -1) fileMap[fp].push(ln);
                }
            });
            if (Object.keys(fileMap).length > 0) {
                lines.push('modifications:');
                Object.keys(fileMap).sort().forEach(function(fp) {
                    var sorted = fileMap[fp].sort(function(a, b) { return a - b; });
                    lines.push('  - file: ' + fp);
                    lines.push('    lines: [' + sorted.join(', ') + ']');
                });
            }
        }
    }

    // Annotations section for drawn shapes
    if (drawnFeatures.length > 0) {
        if (lines.length > 0) lines.push('');
        if (drawnFeatures.length === 1 && gdsFeatures.length === 0) {
            // Single drawn shape — flat format
            var sg = getShapeGeom(drawnFeatures[0]);
            lines = lines.concat(shapeToYAML(sg));
        } else {
            // Multiple drawn or mixed — list format
            lines.push('annotations:');
            drawnFeatures.forEach(function(f) {
                var sg = getShapeGeom(f);
                lines.push('  - shape: ' + sg.type);
                if (sg.bbox) lines.push('    bbox: ' + JSON.stringify(sg.bbox));
                if (sg.width !== undefined) lines.push('    width: ' + sg.width);
                if (sg.height !== undefined) lines.push('    height: ' + sg.height);
                if (sg.center) lines.push('    center: ' + JSON.stringify(sg.center));
                if (sg.radius !== undefined) lines.push('    radius: ' + sg.radius);
                if (sg.length !== undefined) lines.push('    length: ' + sg.length);
                if (sg.area !== undefined) lines.push('    area: ' + sg.area);
            });
        }
    }

    if (lines.length === 0) {
        lines = ['# No data to copy'];
    }

    copyToClipboard(lines.join('\n'));
}
```

- [ ] **Step 3: Verify YAML copy**

Draw a rectangle, select it, click Copy YAML. Verify output matches the spec format. Draw a circle, select both, Copy YAML. Verify annotations format. Select a GDS polygon + drawn shape, Copy YAML. Verify mixed format.

- [ ] **Step 4: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): YAML output for drawn shapes with mixed selection support"
```

---

### Task 7: Delete drawn shapes

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Add deleteDrawn function**

Add after `setMode`:

```javascript
function deleteDrawn() {
    var drawn = selectedFeatures.getArray().filter(function(f) { return f.get('isDrawn'); });
    if (drawn.length === 0) return;
    drawn.forEach(function(f) {
        selectedFeatures.remove(f);
        drawSource.removeFeature(f);
    });
    drawLayer.changed();
    onSelectionChanged();
}
```

- [ ] **Step 2: Add Delete/Backspace key handler**

In the existing keydown listener, add after the Escape handler:

```javascript
if (e.key === 'Delete' || e.key === 'Backspace') {
    // Only delete drawn shapes, not GDS polygons
    if (selectedFeatures.getArray().some(function(f) { return f.get('isDrawn'); })) {
        e.preventDefault();
        deleteDrawn();
    }
}
```

- [ ] **Step 3: Verify delete works**

Draw a shape, select it, press Delete. Shape should disappear. Select a GDS polygon, press Delete — nothing should happen.

- [ ] **Step 4: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): delete drawn shapes with Delete key and toolbar button"
```

---

### Task 8: Snap functionality

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Add grid source and snap state**

Add after `translateInteraction`:

```javascript
// Snap
var gridSource = new ol.source.Vector();
var snapGds = new ol.interaction.Snap({ source: source, pixelTolerance: 10 });
var snapDraw = new ol.interaction.Snap({ source: drawSource, pixelTolerance: 10 });
var snapGrid = new ol.interaction.Snap({ source: gridSource, pixelTolerance: 10 });
snapGds.setActive(false);
snapDraw.setActive(false);
snapGrid.setActive(false);
map.addInteraction(snapGds);
map.addInteraction(snapDraw);
map.addInteraction(snapGrid);
```

- [ ] **Step 2: Add toggleSnap function**

```javascript
function toggleSnap() {
    snapActive = !snapActive;
    snapGds.setActive(snapActive);
    snapDraw.setActive(snapActive);
    snapGrid.setActive(snapActive);

    var btn = document.querySelector('.tool-btn[data-mode="snap"]');
    btn.classList.toggle('active', snapActive);

    if (snapActive) {
        updateGridSnap();
    }
}
```

- [ ] **Step 3: Add grid snap update function**

```javascript
function updateGridSnap() {
    if (!snapActive) return;

    var view = map.getView();
    var resolution = view.getResolution();
    var extent = view.calculateExtent(map.getSize());

    // Compute grid spacing: round to nearest power of 10 in map units
    // so that grid lines are ~50-100px apart
    var rawSpacing = resolution * 80;
    var exponent = Math.floor(Math.log10(rawSpacing));
    var spacing = Math.pow(10, exponent);

    var minX = Math.floor(extent[0] / spacing) * spacing;
    var minY = Math.floor(extent[1] / spacing) * spacing;
    var maxX = Math.ceil(extent[2] / spacing) * spacing;
    var maxY = Math.ceil(extent[3] / spacing) * spacing;

    // Limit grid points to prevent performance issues
    var maxPoints = 2000;
    var countX = Math.round((maxX - minX) / spacing) + 1;
    var countY = Math.round((maxY - minY) / spacing) + 1;
    if (countX * countY > maxPoints) return;

    gridSource.clear();
    for (var x = minX; x <= maxX; x += spacing) {
        for (var y = minY; y <= maxY; y += spacing) {
            var pt = new ol.Feature({ geometry: new ol.geom.Point([x, y]) });
            gridSource.addFeature(pt);
        }
    }
}
```

- [ ] **Step 4: Listen for view changes to update grid**

Add after `updateGridSnap`:

```javascript
map.getView().on('change:resolution', function() {
    if (snapActive) updateGridSnap();
});
map.on('moveend', function() {
    if (snapActive) updateGridSnap();
});
```

- [ ] **Step 5: Verify snap works**

Activate snap button (should highlight). Draw a rectangle near a GDS polygon edge — should snap to it. Zoom in and draw — should snap to grid points. Toggle snap off — no more snapping.

- [ ] **Step 6: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): snap to grid and features with toggle"
```

---

### Task 9: Keyboard shortcuts

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Add keyboard shortcut handlers**

In the existing keydown listener, add before the closing `});`:

```javascript
if (e.key === '1') setMode('select');
if (e.key === '2') setMode('rectangle');
if (e.key === '3') setMode('circle');
if (e.key === '4') setMode('line');
if (e.key === '5') setMode('polygon');
if (e.key === 's' || e.key === 'S') {
    if (!e.ctrlKey && !e.metaKey) toggleSnap();
}
```

Note: Check that these only fire when not typing in an input field. Since the viewer has no text inputs, this is safe.

- [ ] **Step 2: Verify all keyboard shortcuts**

Press 1-5 to switch modes. Press S to toggle snap. Press Delete to delete selected drawn shape. Press Escape to clear selection and return to select mode.

- [ ] **Step 3: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): keyboard shortcuts for mode switching and snap toggle"
```

---

### Task 10: Final cleanup and integration testing

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Verify drawn shapes persist across GDS file switches**

Draw some shapes. Click a different GDS file in the sidebar. Drawn shapes should still be on the map.

- [ ] **Step 2: Verify all interaction modes don't conflict**

Test the following sequences:
- Select mode → click GDS polygon → info shows provenance
- Select mode → click drawn shape → info shows shape properties
- Draw mode → draw shape → auto-switch to select → shape is selected
- Select mode → Ctrl+click GDS + drawn → mixed info shown
- Draw mode → Escape → back to select mode, drawing cancelled

- [ ] **Step 3: Verify YAML copy for all combinations**

- Single GDS polygon → original YAML format
- Single drawn shape → shape YAML with coordinates
- Multiple GDS → file-aggregated modifications
- Multiple drawn → annotations list
- Mixed → modifications + annotations

- [ ] **Step 4: Final commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): complete drawing toolbar with shapes, editing, snap, and YAML export"
```
