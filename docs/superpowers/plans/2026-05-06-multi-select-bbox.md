# Multi-Select BBox Display Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When multiple GDS components are selected, display each component's bbox in the info panel sorted by line number.

**Architecture:** Modify `showMultiInspect()` to collect bbox data from each feature, sort by line number, and display in format: `{filename} Component N: Line {line}, bbox:[xmin, ymin, xmax, ymax]`

**Tech Stack:** Vanilla JavaScript (viewer.html only)

---

## Task 1: Add bbox display to showMultiInspect

**Files:**
- Modify: `gds-services/parser/viewer.html:291-321` (showMultiInspect function)

- [ ] **Step 1: Read current showMultiInspect function**

```javascript
// Lines 275-321 in viewer.html
function showMultiInspect(features) {
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

    var fileMap = {};
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

    updateMultiSourcePanel(fileMap);
}
```

- [ ] **Step 2: Add component list section after file/line info (after line 313)**

Replace lines 302-313 with:

```javascript
    addSep(panel);

    // Build component list with bbox sorted by line number
    var componentList = [];
    features.forEach(function(f) {
        var prov = f.get('provenance') || {};
        var meta = f.get('meta') || {};
        var bbox = meta.bbox || [];
        if (prov.file && prov.line) {
            componentList.push({
                file: prov.file.replace(/\\/g, '/'),
                line: parseInt(prov.line),
                bbox: bbox
            });
        }
    });

    // Sort by line number
    componentList.sort(function(a, b) { return a.line - b.line; });

    // Display each component with bbox
    if (componentList.length > 0) {
        addKV(panel, 'components', componentList.length + ' component(s) with bbox');
        componentList.forEach(function(comp, idx) {
            var base = comp.file.split('/').pop();
            var bboxStr = '[' + comp.bbox.map(function(v) { return v.toFixed(4); }).join(', ') + ']';
            addKV(panel, '', base + ' Component ' + (idx + 1) + ': Line ' + comp.line + ', bbox:' + bboxStr);
        });
    }

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
```

- [ ] **Step 3: Test locally**

Open viewer.html in browser, select multiple GDS components, verify bbox displays per component sorted by line number.

- [ ] **Step 4: Commit**

```bash
git add gds-services/parser/viewer.html
git commit -m "feat(viewer): show bbox for each component in multi-select"
```
