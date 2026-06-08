# Phase 0 — Backend Wrap-up & Go-Live Runbook

**Date:** 2026-06-08
**Author:** Henry (henry@anchorpointrisk.co.za)
**Goal:** Merge the finished Plan 3 backend to `main`, apply its migrations to the production Supabase project, get the FastAPI service live on Render, and configure OAuth — so the Plan 4 web UI is built against a real, live backend (Approach A).

This is an **operational checklist**, not a build. Steps marked **[manual]** must be done by hand in a dashboard; steps marked **[scriptable]** can be run from the terminal. Do them in order.

---

## Pre-flight

- [ ] Confirm `plan-3-imports-exports` is the current branch and the working tree is clean (`git status`).
- [ ] Confirm Plan 3 unit tests pass locally: `cd packages/api && uv run pytest -m "not integration"` (expect 80 passed).
- [ ] Confirm you have: Supabase project ref + DB connection string, the `SUPABASE_SERVICE_ROLE_KEY` and `SUPABASE_JWT_SECRET`, and Render dashboard access.

## Step 1 — Merge Plan 3 to `main`  [scriptable]

Plan 3 is built directly on Plan 2, which is already merged, so this is a clean fast-forward-style merge.

- [ ] `git checkout main && git pull`
- [ ] `git merge --no-ff plan-3-imports-exports -m "Merge plan-3-imports-exports into main"`
- [ ] `git push origin main`
- [ ] Confirm CI (`.github/workflows/api.yml`) goes green on `main` — this is the run that exercises the WeasyPrint PDF tests on Linux.

## Step 2 — Apply Plan 3 migrations to production Supabase  [scriptable]

Five additive migrations ship with Plan 3 (`supabase/migrations/20260503000001..05`): `pg_trgm` + GIN index, `import_batch`, `import_item`, imports RLS, storage bucket.

- [ ] Dry-run review the SQL files so you know exactly what runs.
- [ ] `supabase db push --db-url "<prod-db-url>"` (applies any unapplied migrations).
- [ ] Verify in the Supabase SQL editor: `import_batch` and `import_item` tables exist, `pg_trgm` extension is enabled, and RLS is **on** for both new tables.
- [ ] Migrations are additive — safe to leave applied even if you later roll the API back.

## Step 3 — Confirm the `imports` Storage bucket  [manual]

- [ ] In the Supabase dashboard → Storage, confirm an `imports` bucket exists (created by `20260503000005_storage_bucket.sql`; verify the migration's bucket policy applied — if the dashboard shows the bucket but no policies, re-check the migration ran).
- [ ] Bucket should be **private** (signed-URL access only; the API mints signed URLs with `STORAGE_SIGNED_URL_TTL_S`).

## Step 4 — Deploy the API on Render (Docker path)  [manual + scriptable]

Render builds from `packages/api/Dockerfile` (`env: docker` in `packages/api/render.yaml`); the Dockerfile installs WeasyPrint's native deps (Pango/Cairo/etc.).

- [ ] In Render, confirm the Web Service points at this repo + the Docker build path. (If the service doesn't exist yet, create it from `render.yaml`.)
- [ ] Set environment variables in the Render dashboard (secrets are NOT in render.yaml):
  - `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
  - `BRANDING_FIRM_NAME`, `BRANDING_FIRM_ADDRESS_LINES`, `BRANDING_FIRM_CONTACT_LINES`, `BRANDING_FIRM_LOGO_PATH`
  - `IMPORT_MAX_FILE_BYTES`, `STORAGE_SIGNED_URL_TTL_S`, `DB_ACQUIRE_TIMEOUT_S`
  - `ALLOWED_ORIGINS` — **must include the web app origin(s)**: `http://localhost:5173` (dev) and the future Render Static Site URL (prod). Update this again in Phase 5 once the web URL is known.
- [ ] Trigger a deploy. Watch the build log for a clean WeasyPrint import (no missing-lib errors).
- [ ] Confirm `GET /healthz` returns 200 on the live URL.

## Step 5 — Configure OAuth in Supabase  [manual]

Not yet configured. The web app uses the Supabase JS client for Google / Microsoft OAuth.

- [ ] **Google:** create OAuth credentials in Google Cloud Console; add the Supabase callback URL (`https://<project-ref>.supabase.co/auth/v1/callback`) as an authorized redirect URI. Paste client ID/secret into Supabase → Authentication → Providers → Google.
- [ ] **Microsoft (optional if Google-only at launch):** same flow via Azure app registration; enable the Azure provider in Supabase.
- [ ] In Supabase → Authentication → URL Configuration, add the web app's Site URL and additional redirect URLs: `http://localhost:5173` and the prod web URL.
- [ ] Sanity check: from a scratch page or the Supabase dashboard, complete one OAuth round-trip and confirm a row appears in `auth.users`.
- [ ] Confirm the new user is mirrored into `app_user` with a role. **Role assignment is manual in v1** (Supabase dashboard / SQL) — set your own user to `valuer`.

## Step 6 — Smoke test  [scriptable]

- [ ] Grab a real JWT (from a completed OAuth session, or mint one with the JWT secret for testing).
- [ ] `bash packages/api/scripts/smoke.sh <LIVE_BASE_URL> <JWT>` — exercises core endpoints plus `/imports` and the export endpoints.
- [ ] Spot-check one export by hand: `GET /snapshots/{id}/export.pdf` returns `application/pdf` (requires at least one snapshot to exist — create one via `POST /properties/{id}/snapshots` or an import first).

## Exit criteria

- [ ] `main` contains Plan 3; CI green.
- [ ] Prod Supabase has all migrations + the `imports` bucket.
- [ ] API live on Render; `/healthz` 200; smoke script passes.
- [ ] OAuth works end-to-end; your user is a `valuer` in `app_user`.
- [ ] `ALLOWED_ORIGINS` includes `http://localhost:5173` (so Phase 1 web dev can call the live API).

Once these are all checked, proceed to the Plan 4 web-UI build.

## Rollback notes

- API: Render one-click previous deploy.
- Migrations are additive and safe to leave applied during an API rollback. Orphaned `import_batch`/`import_item` rows and the `imports` bucket are harmless.
