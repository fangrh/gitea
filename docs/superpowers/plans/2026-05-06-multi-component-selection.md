# Multi-Component Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Ctrl+click multi-select and DragBox area selection to the GDS viewer, with file-aggregated YAML output and collapsible source code panel.

**Architecture:** Extend the existing OpenLayers `Select` interaction to support multi-mode, add a `DragBox` interaction for area selection, and refactor the console panel to display aggregated YAML and per-file collapsible source code. All changes are in a single file (`viewer.html`).

**Tech Stack:** OpenLayers 10, vanilla JavaScript, FastAPI backend (no changes)

---

### Task 1: Add state variables and Ctrl key tracking

**Files:**
- Modify: `gds-services/parser/viewer.html:74-80` (state variables section)

- [ ] **Step 1: Replace single-feature state with collection-based state**

Replace lines 77-79 (the `selectedFeature`, `currentProvenance`, `activeTab` block) with:

```javascript
var selectedFeatures = new ol.Collection();
var ctrlPressed = false;
var activeTab = 'info';
var sourceCache = {};   // filePath -> source code string
var expandedFiles = {}; // filePath -> true/false
```

- [ ] **Step 2: Add keydown/keyup listeners for Ctrl key tracking**

Add after the state variables, before the `gdsGeoJsonFmt` declaration:

```javascript
document.addEventListener('keydown', function(e) {
    if (e.key === 'Control' || e.key === 'Meta') ctrlPressed = true;
    if (e.key === 'Escape') clearSelection();
});
document.addEventListener('keyup', function(e) {
    if (e.key === 'Control' || e.key === 'Meta') ctrlPressed = false;
});
```

- [ ] **Step 3: Add helper functions for selection management**

Add after the keydown/keyup listeners:

```javascript
function addToSelection(features) {
    features.forEach(function(f) {
        if (!selectedFeatures.getArray().includes(f)) {
            selectedFeatures.push(f);
            f.set('selected', true);
        }
    });
}

function removeFromSelection(features) {
    features.forEach(function(f) {
        selectedFeatures.remove(f);
        f.set('selected', false);
    });
}

function replaceSelection(features) {
    selectedFeatures.forEach(function(f) { f.set('selected', false); });
    selectedFeatures.clear();
    features.forEach(function(f) {
        selectedFeatures.push(f);
        f.set('selected', true);
    });
}

function clearSelection() {
    selectedFeatures.forEach(function(f) { f.set('selected', false); });
    selectedFeatures.clear();
    vectorLayer.changed();
    onSelectionChanged();
}
```

- [ ] **Step 4: Add stub `onSelectionChanged` function**

Add after the selection helpers:

```javascript
function onSelectionChanged() {
    // Will be implemented in Task 5
}
```

- [ ] **Step 5: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): add multi-select state management and Ctrl key tracking"
```

---

### Task 2: Replace Select interaction with multi-select

**Files:**
- Modify: `gds-services/parser/viewer.html:120-145` (select interaction section)

- [ ] **Step 1: Replace the Select interaction and its event handler**

Replace lines 120-145 (from `// Select interaction` through the closing `});`) with:

```javascript
// Select interaction — multi-select capable
var selectClick = new ol.interaction.Select({
    layers: [vectorLayer],
    style: null,  // use layer style function
    multi: true
});
map.addInteraction(selectClick);

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
        // Clicked empty space
        clearSelection();
        return;
    }

    // Clear the internal Select collection so it doesn't accumulate
    selectClick.getFeatures().clear();
    vectorLayer.changed();
    onSelectionChanged();
});
```

- [ ] **Step 2: Verify single-click still works**

Open the viewer in a browser, load a GDS file, click a polygon. Verify it highlights. Click another — the first should deselect and the new one should highlight. Click empty space — all should deselect.

- [ ] **Step 3: Verify Ctrl+click multi-select works**

Click a polygon, then Ctrl+click another. Both should be highlighted. Ctrl+click a selected polygon — it should deselect. Release Ctrl and click a new polygon — only the new one should be selected.

- [ ] **Step 4: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): multi-select via Ctrl+click with toggle behavior"
```

---

### Task 3: Add DragBox interaction for area selection

**Files:**
- Modify: `gds-services/parser/viewer.html` (after the selectClick handler)

- [ ] **Step 1: Add DragBox interaction**

Add after the `selectClick` handler block (after the `onSelectionChanged();` line):

```javascript
// DragBox interaction for area selection
var dragBox = new ol.interaction.DragBox({
    condition: function(mapBrowserEvent) {
        // Only trigger on left mouse button drag (no modifier required)
        return ol.events.condition.mouseActionButton(mapBrowserEvent) &&
               ol.events.condition.noModifierKeys(mapBrowserEvent) ||
               ol.events.condition.platformModifierKeyOnly(mapBrowserEvent);
    }
});
map.addInteraction(dragBox);

var dragStartPixel = null;

dragBox.on('boxstart', function(e) {
    dragStartPixel = e.pixel;
});

dragBox.on('boxend', function(e) {
    var extent = dragBox.getGeometry().getExtent();
    var dragDist = Math.sqrt(
        Math.pow(e.pixel[0] - dragStartPixel[0], 2) +
        Math.pow(e.pixel[1] - dragStartPixel[1], 2)
    );

    // If drag distance < 5px, treat as click — let Select handle it
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

    if (ctrlPressed) {
        addToSelection(featuresInBox);
    } else {
        replaceSelection(featuresInBox);
    }

    vectorLayer.changed();
    onSelectionChanged();
});
```

- [ ] **Step 2: Add DragBox CSS style**

Add inside the `<style>` block (before `</style>`):

```css
.ol-dragbox { border: 2px dashed #89b4fa !important; background-color: rgba(137,180,250,0.1) !important; }
```

- [ ] **Step 3: Verify box selection works**

Open the viewer, drag a box over multiple polygons. They should all highlight. Then Ctrl+drag another box — those should be added. Drag a box without Ctrl — only the new ones should be selected.

- [ ] **Step 4: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): add DragBox area selection with Ctrl toggle"
```

---

### Task 4: Implement `onSelectionChanged` — info panel for multi-select

**Files:**
- Modify: `gds-services/parser/viewer.html` (replace the stub `onSelectionChanged` and `showInspect`/`clearInspect` functions)

- [ ] **Step 1: Implement `onSelectionChanged`**

Replace the stub `onSelectionChanged` function with:

```javascript
function onSelectionChanged() {
    var features = selectedFeatures.getArray();
    var count = features.length;

    if (count === 0) {
        clearInspect();
        return;
    }

    if (count === 1) {
        showInspect(features[0]);
        return;
    }

    showMultiInspect(features);
}
```

- [ ] **Step 2: Add `showMultiInspect` function**

Add after `onSelectionChanged`:

```javascript
function showMultiInspect(features) {
    // Info panel: aggregated YAML summary
    var panel = document.getElementById('info-panel');
    panel.innerHTML = '';

    var countDiv = document.createElement('div');
    countDiv.className = 'kv';
    countDiv.innerHTML = '<span class="key">selected</span><span class="val">Selected: ' + features.length + ' components</span>';
    panel.appendChild(countDiv);

    if (features.length > 50) {
        var warn = document.createElement('div');
        warn.className = 'kv';
        warn.innerHTML = '<span class="key"></span><span class="val hl">Large selection (' + features.length + ' components). Performance may be affected.</span>';
        panel.appendChild(warn);
    }

    // Aggregate by file
    var fileMap = {}; // file -> [lines]
    features.forEach(function(f) {
        var prov = f.get('provenance') || {};
        if (prov.file && prov.line) {
            var filePath = prov.file.replace(/\\/g, '/');
            if (!fileMap[filePath]) fileMap[filePath] = [];
            var ln = parseInt(prov.line);
            if (fileMap[filePath].indexOf(ln) === -1) fileMap[filePath].push(ln);
        }
    });

    addSep(panel);

    var fileKeys = Object.keys(fileMap);
    if (fileKeys.length > 0) {
        addKV(panel, 'files', fileKeys.length + ' file(s) with provenance');
        fileKeys.forEach(function(fp) {
            var base = fp.split('/').pop();
            addKV(panel, '', base + ': lines [' + fileMap[fp].sort(function(a,b){return a-b;}).join(', ') + ']');
        });
    } else {
        addKV(panel, 'provenance', 'No provenance data in selection');
    }

    addSep(panel);
    addKV(panel, 'repo', repo);
    addKV(panel, 'ref', branch);
    addKV(panel, 'path', currentFilePath);

    // Source panel: collapsible file sections
    updateMultiSourcePanel(fileMap);
}
```

- [ ] **Step 3: Update `clearInspect` to work with new state**

Replace the existing `clearInspect` function:

```javascript
function clearInspect() {
    document.getElementById('info-panel').innerHTML = '<p class="placeholder">Click a polygon to inspect</p>';
    document.getElementById('source-panel').innerHTML = '<p class="placeholder">Click a polygon, then switch to Source tab to view code<br><small style="color:#585b70;">Requires provenance data embedded in the GDS file.</small></p>';
}
```

- [ ] **Step 4: Update `showInspect` to store provenance for source tab**

Replace the existing `showInspect` function:

```javascript
function showInspect(feature) {
    var layer = feature.get('layer') || '?';
    var provenance = feature.get('provenance') || {};
    var meta = feature.get('meta') || {};
    var bbox = meta.bbox || [];

    var panel = document.getElementById('info-panel');
    panel.innerHTML = '';
    var d = frag();
    addKV(d, 'layer', layer);
    addKV(d, 'area', (meta.area_um2 || '?') + ' um2');
    addKV(d, 'bbox', '[' + bbox.map(function(v) { return v.toFixed(4); }).join(', ') + ']');
    addKV(d, 'vertices', String(meta.vertex_count || '?'));

    if (Object.keys(provenance).length > 0) {
        addSep(d);
        if (provenance.instance_name) addKV(d, 'instance', provenance.instance_name, true);
        if (provenance.cell) addKV(d, 'cell', provenance.cell);
        if (provenance.file) addKV(d, 'file', provenance.file + ':' + provenance.line);
        if (provenance.function && provenance.function !== '<module>') addKV(d, 'function', provenance.function + '()');
        if (provenance.class_name) addKV(d, 'class', provenance.class_name);
        if (provenance.call_index) addKV(d, 'call_index', String(provenance.call_index));
    }

    addSep(d);
    addKV(d, 'repo', repo);
    addKV(d, 'ref', branch);
    addKV(d, 'path', currentFilePath);
    panel.appendChild(d);

    // Single-select source panel
    var sp = document.getElementById('source-panel');
    if (provenance.file) {
        var fileMap = {};
        var fp = provenance.file.replace(/\\/g, '/');
        fileMap[fp] = [parseInt(provenance.line)];
        updateMultiSourcePanel(fileMap);
    } else {
        sp.innerHTML = '<p class="placeholder">No provenance data in this GDS file.<br><small style="color:#585b70;">Rebuild the GDS with the latest gdsfactory to enable source inspection.</small></p>';
    }
}
```

- [ ] **Step 5: Verify single-select info panel still works**

Open the viewer, click a single polygon. Info panel should show the same detail as before (layer, area, bbox, provenance).

- [ ] **Step 6: Verify multi-select info panel**

Ctrl+click several polygons. Info panel should show selection count and file-aggregated summary.

- [ ] **Step 7: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): aggregated info panel for multi-select"
```

---

### Task 5: Implement collapsible source code panel

**Files:**
- Modify: `gds-services/parser/viewer.html` (add `updateMultiSourcePanel`, `toggleFileSection`, update `loadSource`)

- [ ] **Step 1: Add CSS for collapsible file sections**

Add inside the `<style>` block:

```css
.file-section { margin: 4px 0; border: 1px solid #313244; border-radius: 4px; }
.file-section-header { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: #181825; cursor: pointer; user-select: none; font-size: 12px; }
.file-section-header:hover { background: #1e1e2e; }
.file-section-header .arrow { color: #585b70; font-size: 10px; transition: transform 0.15s; }
.file-section-header .arrow.open { transform: rotate(90deg); }
.file-section-header .fname { color: #89b4fa; }
.file-section-header .lines { color: #6c7086; margin-left: auto; }
.file-section-body { max-height: 0; overflow: hidden; transition: max-height 0.2s; }
.file-section-body.open { max-height: 400px; overflow-y: auto; }
```

- [ ] **Step 2: Add `updateMultiSourcePanel` function**

Add after `showMultiInspect`:

```javascript
function updateMultiSourcePanel(fileMap) {
    var panel = document.getElementById('source-panel');
    panel.innerHTML = '';

    var fileKeys = Object.keys(fileMap);
    if (fileKeys.length === 0) {
        panel.innerHTML = '<p class="placeholder">No provenance data in selection</p>';
        return;
    }

    fileKeys.forEach(function(fp) {
        var section = document.createElement('div');
        section.className = 'file-section';
        section.setAttribute('data-file', fp);

        var base = fp.split('/').pop();
        var lines = fileMap[fp].sort(function(a,b){return a-b;});
        var isOpen = expandedFiles[fp] || false;

        var header = document.createElement('div');
        header.className = 'file-section-header';
        header.innerHTML = '<span class="arrow' + (isOpen ? ' open' : '') + '">&#9654;</span>'
            + '<span class="fname">' + esc(base) + '</span>'
            + '<span class="lines">lines [' + lines.join(', ') + ']</span>';

        header.onclick = (function(filePath, bodyEl) {
            return function() { toggleFileSection(filePath, bodyEl); };
        })(fp, null); // bodyEl set below

        var body = document.createElement('div');
        body.className = 'file-section-body' + (isOpen ? ' open' : '');

        // Re-bind header onclick with correct body reference
        header.onclick = (function(filePath, bodyEl) {
            return function() { toggleFileSection(filePath, bodyEl); };
        })(fp, body);

        if (isOpen) {
            loadFileSource(fp, body, lines);
        } else {
            body.innerHTML = '';
        }

        section.appendChild(header);
        section.appendChild(body);
        panel.appendChild(section);
    });
}
```

- [ ] **Step 3: Add `toggleFileSection` function**

```javascript
function toggleFileSection(filePath, bodyEl) {
    var isOpen = expandedFiles[filePath] || false;
    expandedFiles[filePath] = !isOpen;

    var section = bodyEl.parentElement;
    var arrow = section.querySelector('.arrow');
    if (!isOpen) {
        // Opening
        bodyEl.classList.add('open');
        arrow.classList.add('open');
        // Get lines from the section header
        var linesText = section.querySelector('.lines').textContent;
        var match = linesText.match(/\[(.+)\]/);
        var lines = match ? match[1].split(', ').map(Number) : [];
        loadFileSource(filePath, bodyEl, lines);
    } else {
        // Closing
        bodyEl.classList.remove('open');
        arrow.classList.remove('open');
    }
}
```

- [ ] **Step 4: Add `loadFileSource` function (with caching)**

```javascript
function loadFileSource(filePath, container, highlightLines) {
    if (sourceCache[filePath]) {
        renderSourceLines(sourceCache[filePath], container, highlightLines);
        return;
    }

    container.innerHTML = '<p class="placeholder" style="padding:8px;">Loading...</p>';

    var url = '/source?repo=' + encodeURIComponent(repo) + '&ref=' + branch
        + '&path=' + encodeURIComponent(filePath);

    fetch(url).then(function(r) {
        if (!r.ok) throw Error('HTTP ' + r.status);
        return r.text();
    }).then(function(code) {
        sourceCache[filePath] = code;
        renderSourceLines(code, container, highlightLines);
    }).catch(function(e) {
        container.innerHTML = '<p class="placeholder">Failed to load source: ' + esc(e.message) + '</p>';
    });
}
```

- [ ] **Step 5: Add `renderSourceLines` helper**

```javascript
function renderSourceLines(code, container, highlightLines) {
    var lines = code.split('\n');
    var html = '';
    for (var i = 0; i < lines.length; i++) {
        var ln = i + 1;
        var cls = highlightLines.indexOf(ln) !== -1 ? 'src-line hl' : 'src-line';
        html += '<div class="' + cls + '"><span class="ln">' + ln + '</span><span class="code">' + esc(lines[i]) + '</span></div>';
    }
    container.innerHTML = html;

    // Auto-scroll to first highlighted line
    var firstHl = container.querySelector('.src-line.hl');
    if (firstHl) {
        firstHl.scrollIntoView({ block: 'center' });
    }
}
```

- [ ] **Step 6: Remove old `loadSource` function**

Delete the existing `loadSource` function (lines 327-362). It is replaced by `loadFileSource` + `renderSourceLines`.

- [ ] **Step 7: Update `switchTab` to work with new source panel**

Replace the existing `switchTab` function:

```javascript
function switchTab(e, tab) {
    e.stopPropagation();
    activeTab = tab;
    document.querySelectorAll('.tab-btn').forEach(function(b) {
        b.classList.toggle('active', b.dataset.tab === tab);
    });
    document.getElementById('info-panel').style.display = tab === 'info' ? '' : 'none';
    document.getElementById('source-panel').style.display = tab === 'source' ? '' : 'none';
}
```

Note: The old `if (tab === 'source' && currentProvenance.file) { loadSource(); }` call is no longer needed because `updateMultiSourcePanel` is called by `onSelectionChanged` when selection changes.

- [ ] **Step 8: Clear source cache on file change**

In the `loadGDS` function, add `sourceCache = {};` and `expandedFiles = {};` after `source.clear();` (around line 185):

```javascript
source.clear();
allFeatures = [];
layerColors = {};
sourceCache = {};
expandedFiles = {};
```

- [ ] **Step 9: Verify collapsible source panel**

Open viewer, Ctrl+click 3-4 polygons from different files. Switch to Source tab. Should see collapsible sections, default collapsed. Click to expand — source code loads with highlighted lines. Collapse and expand again — should use cache (no second request). Change selection — panel refreshes, expanded files that are still in selection stay expanded.

- [ ] **Step 10: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): collapsible source code panel grouped by file"
```

---

### Task 6: Update copyYAML for multi-select

**Files:**
- Modify: `gds-services/parser/viewer.html` (replace `copyYAML` function)

- [ ] **Step 1: Replace `copyYAML` function**

Replace the existing `copyYAML` function with:

```javascript
function copyYAML(e) {
    e.stopPropagation();
    var features = selectedFeatures.getArray();
    if (features.length === 0) return;

    if (features.length === 1) {
        // Single selection: original format
        var f = features[0];
        var layer = f.get('layer') || '?';
        var provenance = f.get('provenance') || {};
        var meta = f.get('meta') || {};
        var bbox = (meta.bbox || []).map(function(v) { return v.toFixed(4); });

        var lines = [
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

        copyToClipboard(lines.join('\n'));
    } else {
        // Multi selection: file-aggregated format
        var fileMap = {};
        features.forEach(function(f) {
            var prov = f.get('provenance') || {};
            if (prov.file && prov.line) {
                var fp = prov.file.replace(/\\/g, '/');
                if (!fileMap[fp]) fileMap[fp] = [];
                var ln = parseInt(prov.line);
                if (fileMap[fp].indexOf(ln) === -1) fileMap[fp].push(ln);
            }
        });

        var lines = ['modifications:'];
        Object.keys(fileMap).sort().forEach(function(fp) {
            var sorted = fileMap[fp].sort(function(a,b){return a-b;});
            lines.push('  - file: ' + fp);
            lines.push('    lines: [' + sorted.join(', ') + ']');
        });

        if (lines.length === 1) {
            // No provenance in any selected feature
            lines = ['# No provenance data in selection'];
        }

        copyToClipboard(lines.join('\n'));
    }
}
```

- [ ] **Step 2: Verify YAML copy for single selection**

Click one polygon, click Copy YAML. Verify output is the original format.

- [ ] **Step 3: Verify YAML copy for multi selection**

Ctrl+click multiple polygons, click Copy YAML. Verify output is the aggregated format:
```
modifications:
  - file: ring.py
    lines: [12, 45]
  - file: waveguide.py
    lines: [34, 56]
```

- [ ] **Step 4: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): file-aggregated YAML output for multi-select"
```

---

### Task 7: Final cleanup and edge case testing

**Files:**
- Modify: `gds-services/parser/viewer.html`

- [ ] **Step 1: Verify Esc key clears selection**

Select multiple polygons, press Esc. All should deselect.

- [ ] **Step 2: Verify large selection warning**

If the GDS has enough polygons, Ctrl+drag to select >50. Verify warning appears in info panel.

- [ ] **Step 3: Verify features without provenance**

Select a feature that has no provenance data. Verify it's counted but not in YAML output.

- [ ] **Step 4: Verify source fetch failure**

Temporarily break the `/source` URL (e.g., set a bad repo name) and expand a file section. Verify "Failed to load source" message appears.

- [ ] **Step 5: Verify source cache is cleared on file change**

Load one GDS file, expand source sections. Load a different GDS file. Verify source panel resets.

- [ ] **Step 6: Final commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): complete multi-component selection with Ctrl+click and DragBox"
```
