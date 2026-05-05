// Copyright 2026 The Gitea Authors. All rights reserved.
// SPDX-License-Identifier: MIT

package setting

// GDSViewer settings
var (
	GDSViewer = struct {
		Enabled   bool
		IframeURL string
		ParserURL string
	}{
		Enabled: false,
	}
)

func loadGDSViewerFrom(rootCfg ConfigProvider) {
	sec, _ := rootCfg.GetSection("gds_viewer")
	if sec == nil {
		return
	}
	GDSViewer.Enabled = sec.Key("ENABLED").MustBool(false)
	GDSViewer.IframeURL = sec.Key("IFRAME_URL").MustString("")
	GDSViewer.ParserURL = sec.Key("PARSER_URL").MustString("http://gds-parser:8000")
}
