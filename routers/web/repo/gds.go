// Copyright 2026 The Gitea Authors. All rights reserved.
// SPDX-License-Identifier: MIT

package repo

import (
	"net/http"
	"net/url"

	"code.gitea.io/gitea/modules/setting"
	"code.gitea.io/gitea/modules/templates"
	"code.gitea.io/gitea/services/context"
)

const (
	tplGDSViewer templates.TplName = "repo/gds"
)

// GDSViewer renders the GDS layout viewer page inside an iframe
func GDSViewer(ctx *context.Context) {
	if !setting.GDSViewer.Enabled {
		ctx.NotFound(nil)
		return
	}

	if setting.GDSViewer.IframeURL == "" {
		ctx.ServerError("GDSViewer URL not configured", nil)
		return
	}

	if ctx.Repo.Repository.IsEmpty || ctx.Repo.Repository.IsBeingCreated() || ctx.Repo.Repository.IsBroken() {
		ctx.Flash.Warning(ctx.Tr("repo.gds_viewer.repo_not_ready"))
		ctx.Redirect(ctx.Repo.RepoLink)
		return
	}

	params := url.Values{}
	params.Set("repo", ctx.Repo.Repository.FullName())
	params.Set("branch", ctx.Repo.BranchName)

	ctx.Data["Title"] = ctx.Tr("repo.gds_viewer")
	ctx.Data["PageIsGDSViewer"] = true
	ctx.Data["GDSIframeURL"] = setting.GDSViewer.IframeURL + "?" + params.Encode()
	ctx.HTML(http.StatusOK, tplGDSViewer)
}
