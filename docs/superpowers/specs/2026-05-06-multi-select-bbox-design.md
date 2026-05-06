# Multi-Select BBox Display Design

## Overview

When multiple GDS components are selected in the viewer, display each component's bbox in the info panel with file, line number, and bbox coordinates. Format is optimized for AI parsing.

## Problem

Currently `showMultiInspect()` only shows file/line provenance for multi-select but does not display bbox information. Single component selection shows bbox via `showInspect()`.

## Solution

Modify `showMultiInspect()` to display bbox for each selected component after the file summary section.

## Format

Each component displayed as:
```
{filename} Component N: Line {line}, bbox:[{xmin}, {ymin}, {xmax}, {ymax}]
```

Example:
```
design.py Component 1: Line 12, bbox:[1.2340, 2.3450, 3.4560, 4.5670]
design.py Component 2: Line 45, bbox:[5.6780, 6.7890, 7.8900, 8.9010]
```

Components sorted by line number ascending.

## Implementation

Modify `gds-services/parser/viewer.html` - `showMultiInspect()` function:

1. After the file/line provenance section, add separator
2. Build array of {filename, line, bbox} for each feature
3. Sort by line number
4. Display each component with bbox

Data source: `feature.get('meta').bbox` and `feature.get('provenance')`.
