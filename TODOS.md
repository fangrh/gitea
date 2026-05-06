# TODOS

## Deferred from GDS Viewer v1

### Add empty IFRAME_URL check in GDS handler
- **Why:** If `IFRAME_URL` config key is missing/empty, the handler constructs `?repo=...&branch=...` as the iframe src, producing a silent blank iframe with no error message.
- **Pros:** Prevents hard-to-debug silent failure. Operator sees a clear 500 error instead.
- **Cons:** One extra if statement in the handler (~4 lines).
- **Context:** `routers/web/repo/gds.go` — add check after reading `setting.GDSViewer.IframeURL`, before URL construction. Return `ctx.ServerError("GDS Viewer URL not configured", err)` if empty.
- **Depends on:** Nothing

### Add Playwright E2E tests for GDS Viewer tab
- **Why:** Verify tab visibility when enabled/disabled, iframe loads on click, 404 when disabled. Manual testing is sufficient for v1 internal use, but automated tests prevent regressions.
- **Pros:** Catches regressions when Gitea's template/route system changes. Confirms the full integration chain works (config → route → template → iframe).
- **Cons:** Requires Playwright setup with Gitea test fixtures. ~30-40 lines of test code.
- **Context:** Add to `tests/e2e/` following existing patterns. Test: (1) enable config, open repo, verify tab exists and page loads; (2) disable config, verify tab hidden, /gds returns 404.
- **Depends on:** Feature implementation complete

### Support per-repo GDS viewer toggle via unit type
- **Why:** v1 uses a global config flag. Some repos may not contain GDS files and shouldn't show the tab.
- **Pros:** Cleaner UX — tab only appears on repos that actually use GDS files. Follows Gitea's unit type pattern.
- **Cons:** Significant complexity increase — new `TypeGDSViewer` constant, unit type registration, per-repo enable/disable UI, migration.
- **Context:** See `models/unit/unit.go` for existing unit types. Requires adding to `AllRepoUnitTypes` and `DefaultRepoUnits`.
- **Depends on:** v1 validated as useful by the design team

### Add aigds to docker-compose.yml
- **Why:** Production deployment needs both Gitea and aigds running. Keeping them in one compose file simplifies operations.
- **Pros:** One command to start everything. Networking between containers handled automatically.
- **Cons:** aigds isn't dockerized currently. Adds build complexity.
- **Context:** Add `aigds` service to existing `docker-compose.yml` with the FastAPI backend serving both API and built React frontend as static files. Configure `IFRAME_URL` to point to the aigds container.
- **Depends on:** Feature validated as useful; aigds Dockerfile ready
