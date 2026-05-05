// Copyright 2026 The Gitea Authors. All rights reserved.
// SPDX-License-Identifier: MIT

package gdsviewer

import (
	"encoding/binary"
	"fmt"
	"io"
	"math"
)

type gdsRecord struct {
	length   uint16
	recType  byte
	dataType byte
	data     []byte
}

func readRecord(r io.Reader) (*gdsRecord, error) {
	var lenBuf [2]byte
	if _, err := io.ReadFull(r, lenBuf[:]); err != nil {
		return nil, err
	}
	rec := &gdsRecord{}
	rec.length = binary.BigEndian.Uint16(lenBuf[:])
	if rec.length < 4 {
		return nil, fmt.Errorf("invalid record length: %d", rec.length)
	}
	var typeBuf [2]byte
	if _, err := io.ReadFull(r, typeBuf[:]); err != nil {
		return nil, err
	}
	rec.recType = typeBuf[0]
	rec.dataType = typeBuf[1]
	dataLen := int(rec.length) - 4
	if dataLen > 0 {
		rec.data = make([]byte, dataLen)
		if _, err := io.ReadFull(r, rec.data); err != nil {
			return nil, err
		}
	}
	return rec, nil
}

func (r *gdsRecord) int16() int16 {
	if len(r.data) < 2 {
		return 0
	}
	return int16(binary.BigEndian.Uint16(r.data))
}

func (r *gdsRecord) float64At(offset int) float64 {
	return math.Float64frombits(binary.BigEndian.Uint64(r.data[offset:]))
}

func (r *gdsRecord) str() string {
	// GDS strings may be null-terminated or have trailing nulls; trim them
	s := string(r.data)
	for len(s) > 0 && s[len(s)-1] == 0 {
		s = s[:len(s)-1]
	}
	return s
}

type point struct{ X, Y int32 }

type gdsElement struct {
	recType byte
	layer   int16
	dataType int16
	xy      []point
	width   int32
	sname   string
	colRow  [2]int16
}

type gdsCell struct {
	name     string
	elements []gdsElement
}

// ParsedGDS holds the result of parsing a GDSII file
type ParsedGDS struct {
	LibName string
	Cells   map[string]*gdsCell
	UnitDB  float64 // database units per user unit
	UnitM   float64 // meters per database unit
}

// ParseGDS reads a GDSII binary stream and returns parsed data
func ParseGDS(r io.Reader) (*ParsedGDS, error) {
	p := &ParsedGDS{
		Cells: make(map[string]*gdsCell),
	}
	var curCell *gdsCell
	var curEl *gdsElement
	var curXY []point

	for {
		rec, err := readRecord(r)
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, fmt.Errorf("gds parse error: %w", err)
		}

		switch rec.recType {
		case 0x00: // HEADER
		case 0x01: // BGNLIB
		case 0x02: // LIBNAME
			p.LibName = rec.str()
		case 0x03: // UNITS
			if len(rec.data) >= 16 {
				p.UnitDB = rec.float64At(0)
				p.UnitM = rec.float64At(8)
			}
		case 0x04: // ENDLIB
		case 0x05: // BGNSTR
			curCell = &gdsCell{}
		case 0x06: // STRNAME
			if curCell != nil {
				curCell.name = rec.str()
				p.Cells[curCell.name] = curCell
			}
		case 0x07: // ENDSTR
			curCell = nil
		case 0x08: // BOUNDARY
			curEl = &gdsElement{recType: 0x08}
			curXY = nil
		case 0x09: // PATH
			curEl = &gdsElement{recType: 0x09}
			curXY = nil
		case 0x0A: // SREF
			curEl = &gdsElement{recType: 0x0A}
			curXY = nil
		case 0x0B: // AREF
			curEl = &gdsElement{recType: 0x0B}
			curXY = nil
		case 0x0C: // TEXT
			curEl = &gdsElement{recType: 0x0C}
			curXY = nil
		case 0x2D: // BOX
			curEl = &gdsElement{recType: 0x2D}
			curXY = nil
		case 0x0D: // LAYER
			if curEl != nil {
				curEl.layer = rec.int16()
			}
		case 0x0E: // DATATYPE
			if curEl != nil {
				curEl.dataType = rec.int16()
			}
		case 0x0F: // WIDTH
			if curEl != nil && len(rec.data) >= 4 {
				curEl.width = int32(binary.BigEndian.Uint32(rec.data))
			}
		case 0x10: // XY
			n := len(rec.data) / 8
			pts := make([]point, n)
			for i := range n {
				pts[i] = point{
					X: int32(binary.BigEndian.Uint32(rec.data[i*8:])),
					Y: int32(binary.BigEndian.Uint32(rec.data[i*8+4:])),
				}
			}
			curXY = append(curXY, pts...)
		case 0x11: // ENDEL
			if curEl != nil && curCell != nil {
				curEl.xy = curXY
				curCell.elements = append(curCell.elements, *curEl)
			}
			curEl = nil
			curXY = nil
		case 0x12: // SNAME
			if curEl != nil {
				curEl.sname = rec.str()
			}
		case 0x13: // COLROW
			if curEl != nil && len(rec.data) >= 4 {
				curEl.colRow[0] = int16(binary.BigEndian.Uint16(rec.data[0:]))
				curEl.colRow[1] = int16(binary.BigEndian.Uint16(rec.data[2:]))
			}
		case 0x16: // TEXTTYPE
		case 0x17: // PRESENTATION
		case 0x19: // STRING
		case 0x2E: // BOXTYPE
		}
	}
	return p, nil
}

// boundingBox returns the min/max coordinates across all cells
func (p *ParsedGDS) boundingBox() (minX, minY, maxX, maxY int32) {
	minX, minY = int32(math.MaxInt32), int32(math.MaxInt32)
	for _, cell := range p.Cells {
		for _, el := range cell.elements {
			for _, pt := range el.xy {
				if pt.X < minX {
					minX = pt.X
				}
				if pt.Y < minY {
					minY = pt.Y
				}
				if pt.X > maxX {
					maxX = pt.X
				}
				if pt.Y > maxY {
					maxY = pt.Y
				}
			}
		}
	}
	return
}
