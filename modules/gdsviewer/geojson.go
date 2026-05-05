// Copyright 2026 The Gitea Authors. All rights reserved.
// SPDX-License-Identifier: MIT

package gdsviewer

import (
	"encoding/json"
	"math"
)

// ToScaledGeoJSON converts parsed GDS data to GeoJSON FeatureCollection.
// Groups polygons by (layer, datatype). Handles SREF/AREF flattening.
func (p *ParsedGDS) ToScaledGeoJSON() ([]byte, error) {
	scale := p.Scale()
	groups := make(map[[2]int16][][][][]float64)

	for _, cell := range p.Cells {
		for _, el := range cell.elements {
			// SREF/AREF have 1 XY point (placement); BOUNDARY/PATH/BOX have 2+
			if len(el.xy) < 2 && el.recType != 0x0A && el.recType != 0x0B {
				continue
			}

			switch el.recType {
			case 0x08: // BOUNDARY
				groups[[2]int16{el.layer, el.dataType}] = append(
					groups[[2]int16{el.layer, el.dataType}],
					[][][]float64{pointsToScaledCoords(el.xy, scale)},
				)

			case 0x2D: // BOX
				if r := boxToScaledCoords(el.xy, scale); r != nil {
					groups[[2]int16{el.layer, el.dataType}] = append(
						groups[[2]int16{el.layer, el.dataType}],
						[][][]float64{r},
					)
				}

			case 0x09: // PATH
				if len(el.xy) >= 2 {
					halfW := float64(el.width) * scale / 2.0
					if r := pathToScaledCoords(el.xy, scale, halfW); r != nil {
						groups[[2]int16{el.layer, el.dataType}] = append(
							groups[[2]int16{el.layer, el.dataType}],
							[][][]float64{r},
						)
					}
				}

			case 0x0A, 0x0B: // SREF, AREF — flatten referenced cell
				refCell, ok := p.Cells[el.sname]
				if !ok {
					continue
				}
				dx := float64(0)
				dy := float64(0)
				if len(el.xy) > 0 {
					dx = float64(el.xy[0].X) * scale
					dy = float64(el.xy[0].Y) * scale
				}
				for _, refEl := range refCell.elements {
					refKey := [2]int16{refEl.layer, refEl.dataType}
					if len(refEl.xy) < 2 {
						continue
					}
					var r [][]float64
					switch refEl.recType {
					case 0x08:
						r = pointsToScaledCoords(refEl.xy, scale)
					case 0x2D:
						r = boxToScaledCoords(refEl.xy, scale)
					case 0x09:
						halfW := float64(refEl.width) * scale / 2.0
						r = pathToScaledCoords(refEl.xy, scale, halfW)
					default:
						continue
					}
					if r != nil {
						r = offsetScaledCoords(r, dx, dy)
						groups[refKey] = append(groups[refKey], [][][]float64{r})
					}
				}
			}
		}
	}

	return marshalGeoJSON(groups)
}

func marshalGeoJSON(groups map[[2]int16][][][][]float64) ([]byte, error) {
	features := make([]map[string]interface{}, 0, len(groups))
	minX, minY, maxX, maxY := math.MaxFloat64, math.MaxFloat64, -math.MaxFloat64, -math.MaxFloat64

	for key, polys := range groups {
		features = append(features, map[string]interface{}{
			"type": "Feature",
			"geometry": map[string]interface{}{
				"type":        "MultiPolygon",
				"coordinates": polys,
			},
			"properties": map[string]interface{}{
				"layer":     key[0],
				"data_type": key[1],
				"color":     layerColor(key[0], key[1]),
			},
		})

		for _, poly := range polys {
			for _, ring := range poly {
				for _, coord := range ring {
					if len(coord) >= 2 {
						if coord[0] < minX {
							minX = coord[0]
						}
						if coord[1] < minY {
							minY = coord[1]
						}
						if coord[0] > maxX {
							maxX = coord[0]
						}
						if coord[1] > maxY {
							maxY = coord[1]
						}
					}
				}
			}
		}
	}

	output := map[string]interface{}{
		"type":     "FeatureCollection",
		"features": features,
	}
	if len(features) > 0 {
		output["bbox"] = []float64{minX, minY, maxX, maxY}
	}

	return json.Marshal(output)
}

func pointsToScaledCoords(pts []point, scale float64) [][]float64 {
	ring := make([][]float64, len(pts))
	for i, p := range pts {
		ring[i] = []float64{float64(p.X) * scale, float64(p.Y) * scale}
	}
	return ring
}

func boxToScaledCoords(pts []point, scale float64) [][]float64 {
	if len(pts) < 2 {
		return nil
	}
	x1, y1 := float64(pts[0].X)*scale, float64(pts[0].Y)*scale
	x2, y2 := float64(pts[1].X)*scale, float64(pts[1].Y)*scale
	return [][]float64{
		{x1, y1}, {x2, y1}, {x2, y2}, {x1, y2}, {x1, y1},
	}
}

func pathToScaledCoords(pts []point, scale, halfW float64) [][]float64 {
	if len(pts) < 2 {
		return nil
	}
	var ring [][]float64
	for _, p := range pts {
		ring = append(ring, []float64{float64(p.X)*scale - halfW, float64(p.Y)*scale - halfW})
	}
	for i := len(pts) - 1; i >= 0; i-- {
		ring = append(ring, []float64{float64(pts[i].X)*scale + halfW, float64(pts[i].Y)*scale + halfW})
	}
	ring = append(ring, []float64{ring[0][0], ring[0][1]})
	return ring
}

func offsetScaledCoords(ring [][]float64, dx, dy float64) [][]float64 {
	out := make([][]float64, len(ring))
	for i, pt := range ring {
		out[i] = []float64{pt[0] + dx, pt[1] + dy}
	}
	return out
}

func (p *ParsedGDS) Scale() float64 {
	// GDS database units are typically nanometers (UnitDB=0.001).
	// Some GDS writers produce anomalous UNITS records.
	// Fall back to standard 0.001 (1 db unit = 1 nm = 0.001 µm).
	const standardDBPerUserUnit = 0.001
	if p.UnitDB > 0.00001 {
		return p.UnitDB * 1000
	}
	return standardDBPerUserUnit * 1000 // = 1.0: 1nm → 1 EPSG:3857 unit
}

func layerColor(layer, _ int16) string {
	colors := []string{
		"#4ecdc4", "#ff6b6b", "#45b7d1", "#96ceb4",
		"#ffeaa7", "#dfe6e9", "#fd79a8", "#a29bfe",
		"#6c5ce7", "#00b894", "#e17055", "#0984e3",
		"#fab1a0", "#81ecec", "#55efc4", "#74b9ff",
	}
	return colors[int(layer)%len(colors)]
}
