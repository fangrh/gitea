// Copyright 2026 The Gitea Authors. All rights reserved.
// SPDX-License-Identifier: MIT

package repo

import (
	"encoding/json"
	"html/template"
	"net/http"
	"path/filepath"
	"strings"

	"code.gitea.io/gitea/modules/gdsviewer"
	"code.gitea.io/gitea/modules/setting"
	giteaTemplates "code.gitea.io/gitea/modules/templates"
	"code.gitea.io/gitea/services/context"
)

const (
	tplGDSViewer giteaTemplates.TplName = "repo/gds"
)

// GDSViewer renders the GDS layout viewer page
func GDSViewer(ctx *context.Context) {
	if !setting.GDSViewer.Enabled {
		ctx.NotFound(nil)
		return
	}

	if ctx.Repo.Repository.IsEmpty || ctx.Repo.Repository.IsBeingCreated() || ctx.Repo.Repository.IsBroken() {
		ctx.Flash.Warning(ctx.Tr("repo.gds_viewer.repo_not_ready"))
		ctx.Redirect(ctx.Repo.RepoLink)
		return
	}

	gdsFiles := listGDSFiles(ctx)
	gdsFilesJSON, _ := json.Marshal(gdsFiles)
	if gdsFiles == nil {
		gdsFiles = []string{}
		gdsFilesJSON = []byte("[]")
	}
	ctx.Data["GDSFiles"] = gdsFiles
	ctx.Data["GDSFilesJSON"] = template.JS(gdsFilesJSON)
	ctx.Data["Title"] = ctx.Tr("repo.gds_viewer")
	ctx.Data["PageIsGDSViewer"] = true
	ctx.HTML(http.StatusOK, tplGDSViewer)
}

// GDSViewerData serves GDS file geometry as GeoJSON
func GDSViewerData(ctx *context.Context) {
	if !setting.GDSViewer.Enabled {
		ctx.NotFound(nil)
		return
	}

	filePath := ctx.PathParam("filepath")
	if filePath == "" || !strings.HasSuffix(strings.ToLower(filePath), ".gds") {
		ctx.JSON(http.StatusBadRequest, map[string]string{"error": "invalid file path"})
		return
	}

	branchName := ctx.Repo.BranchName
	if branchName == "" {
		branchName = ctx.Repo.Repository.DefaultBranch
	}

	commit, err := ctx.Repo.GitRepo.GetBranchCommit(branchName)
	if err != nil {
		ctx.ServerError("GetBranchCommit", err)
		return
	}

	blob, err := commit.Tree.GetBlobByPath(filePath)
	if err != nil {
		ctx.ServerError("GetBlobByPath", err)
		return
	}

	data, err := blob.GetBlobBytes(100 * 1024 * 1024) // 100MB limit
	if err != nil {
		ctx.ServerError("GetBlobBytes", err)
		return
	}

	parsed, err := gdsviewer.ParseGDS(strings.NewReader(string(data)))
	if err != nil {
		ctx.JSON(http.StatusUnprocessableEntity, map[string]string{"error": "failed to parse GDS file: " + err.Error()})
		return
	}

	geoJSON, err := parsed.ToScaledGeoJSON()
	if err != nil {
		ctx.ServerError("ToGeoJSON", err)
		return
	}

	ctx.Resp.Header().Set("Content-Type", "application/json")
	ctx.Resp.WriteHeader(http.StatusOK)
	ctx.Resp.Write(geoJSON)
}

func listGDSFiles(ctx *context.Context) []string {
	branchName := ctx.Repo.BranchName
	if branchName == "" {
		branchName = ctx.Repo.Repository.DefaultBranch
	}

	commit, err := ctx.Repo.GitRepo.GetBranchCommit(branchName)
	if err != nil {
		return nil
	}

	entries, err := commit.Tree.ListEntriesRecursiveFast()
	if err != nil {
		return nil
	}

	var files []string
	for _, entry := range entries {
		if !entry.IsDir() && !entry.IsSubModule() && strings.HasSuffix(strings.ToLower(entry.Name()), ".gds") {
			files = append(files, filepath.ToSlash(entry.Name()))
		}
	}
	return files
}
