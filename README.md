# Property Valuations Model

Income-capitalisation property valuation engine + web application.

## Packages

- `packages/valuation_engine/` — pure Python valuation engine, **shipped (Plan 1 on `main`)**.
- `packages/api/` — FastAPI service, **Plan 2 complete on branch `plan-2-api-core`**; ready for review / merge.
- `packages/web/` — React UI, **Plan 4 (deferred)**.

## Supporting

- `supabase/` — Supabase CLI config + hand-authored SQL migrations (6 files: app_user, entity, property, valuation_snapshot, audit_log, RLS policies).
- `1. VALUATION EXAMPLES/` — historical workbooks preserved as engine test fixtures.
- `docs/superpowers/specs/` — design specs (top-level + per-plan refinements).
- `docs/superpowers/plans/` — implementation plans.
- `.github/workflows/` — CI workflows (`engine.yml`, `api.yml`).

## Project status

| Plan | Scope | Status |
|---|---|---|
| 1 | `valuation_engine` package + golden + excel parse/render | ✅ Merged to `main` |
| 2 | API core: auth, entities, properties, snapshots, `/calculate`, portfolio, users, audit, tests, CI, Render artifacts | ✅ Complete + live-verified on branch `plan-2-api-core` (46 commits, awaiting merge). End-to-end test against hosted Supabase passed; see [`plan-2 file`](docs/superpowers/plans/2026-04-24-plan-2-api-core.md) "Post-plan-completion log" for the 4 follow-up commits. |
| 3 | Import batches (xlsx upload/review/commit) + PDF export + XLSX export endpoints | ✅ Complete on branch `plan-3-imports-exports` |
| 4 | React web UI | ⏳ Not started |

## Top-level design

See [`docs/superpowers/specs/2026-04-23-property-valuations-model-design.md`](docs/superpowers/specs/2026-04-23-property-valuations-model-design.md).

## Plan-2 handoff notes

- Branch: `plan-2-api-core`. Unit tests pass (`cd packages/api && uv run pytest -m "not integration"` → 38 passed). Ruff + mypy strict clean.
- Integration tests require a local Supabase CLI stack (`supabase start` from repo root, then `uv run pytest` from `packages/api`). Not run in the sandbox that produced the branch.
- Known follow-up TODOs flagged in comments during review:
  - `src/api/db.py`: add acquisition timeout to `pool.acquire()` before production traffic.
  - `src/api/errors.py`: narrow the global `ValueError → 422 engine_validation_error` handler once `/calculate` is the only ValueError source.
- Deploy: Render setup is manual. `packages/api/Dockerfile` + `packages/api/render.yaml` are committed; run `packages/api/scripts/smoke.sh <BASE_URL> <JWT>` post-deploy.

## Plan-3 handoff notes

- Branch: `plan-3-imports-exports`. Unit tests pass (80); ruff + mypy clean.
- Integration tests require a local Supabase CLI stack (Docker). 67 PASS + 3 SKIP locally on Windows; the 3 skipped are PDF render tests that need WeasyPrint native libs (Pango/Cairo). CI runs them on Linux after the apt-install step (`.github/workflows/api.yml`).
- New env vars in production: `BRANDING_FIRM_NAME`, `BRANDING_FIRM_ADDRESS_LINES`, `BRANDING_FIRM_CONTACT_LINES`, `BRANDING_FIRM_LOGO_PATH`, `IMPORT_MAX_FILE_BYTES`, `STORAGE_SIGNED_URL_TTL_S`, `DB_ACQUIRE_TIMEOUT_S`, `SUPABASE_SERVICE_ROLE_KEY`. Set in Render dashboard.
- Apply six new migrations: `supabase db push --db-url <prod-url>`. They are: pg_trgm + GIN index, import_batch, import_item, imports RLS, storage_bucket, audit enum extensions.
- **Deployment model:** Render uses the **Docker build path** (`env: docker` in `render.yaml`, building from `packages/api/Dockerfile`). The Dockerfile installs WeasyPrint native deps (libpango, libcairo, libharfbuzz, libgdk-pixbuf, libpangoft2, fonts-liberation). The Dockerfile is the production build, not a "future fallback" as some commit messages on this branch suggest.
- Rollback: Render one-click previous deploy. Migrations are additive — safe to leave applied during rollback. The `imports` Storage bucket and any `import_batch`/`import_item` rows are orphaned but harmless.
