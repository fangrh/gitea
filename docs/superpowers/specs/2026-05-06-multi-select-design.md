# Multi-Component Selection for GDS Viewer

**Date:** 2026-05-06
**Status:** Draft
**Scope:** `gds-services/parser/viewer.html` (single file change)

## Problem

The GDS viewer currently supports only single-component click selection. Users need to select multiple components simultaneously to generate batch issue provenance for the gds-agent workflow.

## Design

### Interaction Layer

Standard EDA selection logic:

| Action | Without Ctrl | With Ctrl |
|--------|-------------|-----------|
| Click unselected | Replace selection with this item | Add to selection |
| Click selected | Replace selection with this item | Remove from selection |
| Box select area | Replace selection with items in area | Add items in area to selection |
| Click empty space | Clear all | Clear all |

Implementation:

- `Select` interaction with `multi: true`
- `keydown`/`keyup` tracking Ctrl key state
- `ol.interaction.DragBox` for area selection
- DragBox minimum drag distance: 5px (below this, treated as click)
- DragBox visual: blue dashed rectangle (OpenLayers default)
- Unified `onSelectionChanged()` callback handles all downstream rendering
- **Esc key** clears all selection

### Visual Feedback

- All selected items use the existing white stroke + semi-transparent fill style
- Console panel header shows selection count: `Selected: N components`
- Panel behavior by selection state:
  - **No selection:** "Click or drag to select components" (existing)
  - **Single selection:** existing detail view (layer, area, bbox, provenance) — unchanged
  - **Multiple selection:** aggregated YAML summary only, no per-component metadata

### YAML Output

Copy YAML button generates file-aggregated output for multiple selections:

```yaml
modifications:
  - file: ring.py
    lines: [12, 45]
  - file: waveguide.py
    lines: [34, 56, 78]
```

Single selection YAML format remains unchanged from current behavior.

### Source Code Collapsible Panel

Located below the console panel (extending the existing source code area).

Structure per file:

- **Collapsed (default):** shows filename + line numbers
- **Expanded (click to toggle):** fetches source via `/source` endpoint, displays code with all selected lines highlighted (yellow background)

Behavior:

- Multiple files can be expanded simultaneously
- Source code is cached after first fetch (no duplicate requests)
- On selection change, panel refreshes but preserves expanded state for files still in the selection set
- All UI text in English

### Edge Cases

- **Large selection (>50 components):** show warning "Large selection (N components). Performance may be affected." — does not block
- **Features without provenance:** selectable and counted, but excluded from modifications YAML
- **Source fetch failure:** individual file shows "Failed to load source"
- **DragBox < 5px:** treated as click, no box drawn

## File Impact

Only `gds-services/parser/viewer.html` is modified. No backend changes required.

Estimated scope: ~150-200 lines of JavaScript changes within the existing file.
