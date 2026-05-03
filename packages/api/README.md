# api

FastAPI service for the property valuations model.

## Prerequisites

- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv)
- Docker (for the Supabase CLI local stack)
- [Supabase CLI](https://supabase.com/docs/guides/cli)

## Local dev

```bash
# From repo root
supabase start

# In packages/api
cp .env.example .env
uv sync
uv run uvicorn api.main:app --reload
```

API runs on `http://localhost:8000`; Supabase Studio on `http://localhost:54323`.

## Tests

```bash
# Fast unit tests (no Docker required)
uv run pytest -m "not integration"

# All tests (requires `supabase start` running)
uv run pytest
```

## Environment

See `.env.example` for the full list. Required in production:

- `DATABASE_URL` — asyncpg DSN (service-role)
- `SUPABASE_URL`
- `SUPABASE_JWT_SECRET` — HS256 secret for JWT verification
- `ALLOWED_ORIGINS` — comma-separated CORS whitelist

## Deploy

Render Web Service using `Dockerfile` + `render.yaml`. Run `scripts/smoke.sh <BASE_URL> <JWT>` post-deploy.

## Engine dependency

Dev uses the local editable engine via `[tool.uv.sources]`. Release builds (`uv sync --no-sources` or pip with the tagged git ref) resolve to the pinned version from `[project.dependencies]`.

## Plan 3 endpoints

- `POST /imports` — multipart .xlsx upload (valuer-only); returns 202 with batch_id.
- `GET /imports` — list batches with per-status counts.
- `GET /imports/{id}` — batch detail with inline items.
- `PATCH /imports/{id}/items/{iid}` — set resolution + edit inputs (valuer-only).
- `POST /imports/{id}/cancel` — abandon a batch (valuer-only); clears Storage prefix.
- `POST /imports/{id}/commit` — idempotent per-item commit (valuer-only); creates `valuation_snapshot` rows.
- `GET /imports/{id}/items/{iid}/source` — 307 to a 5-minute Supabase Storage signed URL.
- `GET /snapshots/{id}/export.pdf` — WeasyPrint PDF report. Cached via `ETag = snapshot.id` + `Cache-Control: immutable`.
- `GET /snapshots/{id}/export.xlsx` — engine-rendered canonical workbook. Same caching.

See [`docs/superpowers/specs/2026-05-03-plan-3-imports-exports-design.md`](../../docs/superpowers/specs/2026-05-03-plan-3-imports-exports-design.md) for the design and decisions log.

## Plan 3 deployment notes

- The Render deploy uses the Docker build path (`packages/api/Dockerfile`). The Dockerfile installs Pango/Cairo/HarfBuzz/PixBuf for WeasyPrint PDF rendering.
- Six new SQL migrations land with this plan; apply via `supabase db push` against production after merging:
  - `20260503000001_pg_trgm.sql`
  - `20260503000002_import_batch.sql`
  - `20260503000003_import_item.sql`
  - `20260503000004_imports_rls.sql`
  - `20260503000005_storage_bucket.sql`
  - `20260503000006_audit_enum_extensions.sql`
- Eight new env vars (set in Render dashboard before first deploy): `BRANDING_FIRM_NAME`, `BRANDING_FIRM_ADDRESS_LINES`, `BRANDING_FIRM_CONTACT_LINES`, `BRANDING_FIRM_LOGO_PATH`, `IMPORT_MAX_FILE_BYTES`, `STORAGE_SIGNED_URL_TTL_S`, `DB_ACQUIRE_TIMEOUT_S`, `SUPABASE_SERVICE_ROLE_KEY` (the last was missing from Plan 2's render.yaml; it's needed for the Supabase Storage SDK).
- Smoke script `packages/api/scripts/smoke.sh` checks `GET /imports`. Set `SMOKE_SNAPSHOT_ID` env var to also smoke the export endpoints.

## Plan 3 local development

The unit suite runs without Docker:

```bash
cd packages/api
env -u VIRTUAL_ENV uv run --no-sync --extra dev pytest -m "not integration and not pdf"
```

Integration tests require Docker + Supabase CLI:

```bash
supabase start                                    # repo root
cd packages/api
export DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
export SUPABASE_URL=http://localhost:54321
export SUPABASE_JWT_SECRET=$(grep '^jwt_secret' ../../supabase/config.toml | cut -d'"' -f2)
export SUPABASE_SERVICE_ROLE_KEY=$(supabase status -o env | grep SERVICE | cut -d'=' -f2)
env -u VIRTUAL_ENV uv run --no-sync --extra dev pytest -m integration
```

PDF visual tests (`-m pdf`) require WeasyPrint native libs (Pango/Cairo). They skip cleanly on hosts without them.
