# Property Valuations Model — Design

**Date:** 2026-04-23
**Status:** Approved (brainstorming)
**Author:** Henry (henry@anchorpointrisk.co.za)

## 1. Purpose

Build a single-tenant web application that lets valuers produce, store, and report on income-capitalisation property valuations. The calculation logic must live in a versioned Python package so the same engine can be embedded in an existing Render-hosted FastAPI service and pulled into a separate batch pipeline.

The application replaces a workflow currently run in ~130 standalone Excel files (one per property), preserving the canonical layout for round-trip Excel import and export.

## 2. Goals

- Manual UI entry of valuations as the primary input path.
- Bulk Excel import as a batch convenience, with a tolerant parser, recompute-and-compare verification, and a reviewer-driven commit step.
- Immutable, dated valuation snapshots with full year-over-year history and reproducibility (engine version recorded on every snapshot).
- Portfolio dashboard, per-property PDF report, and Excel round-trip export.
- Two-role access (Valuer, Viewer) over Supabase auth (Google / Microsoft OAuth).
- Engine deployable both as a FastAPI dependency and as a standalone Python package consumed by an external pipeline.

## 3. Non-goals (v1)

- Multi-tenant / multi-organisation isolation.
- Multi-currency (ZAR only).
- VAT-aware rent inputs.
- Forward-rolling 12-month average rent (engine capitalises rent on `valuation_date` only).
- Draft/publish workflow on snapshots.
- Custom user-defined property fields.
- File attachments (lease PDFs, photos, deeds).
- Scheduled / emailed reports.
- Admin role for in-app user management (role assignment is done in the Supabase dashboard).

## 4. Architecture

Monorepo, three packages:

```
property-valuations-model/
├── packages/
│   ├── valuation_engine/     # pure Python, semver, no I/O, no DB
│   ├── api/                  # FastAPI service
│   └── web/                  # React (Vite + TypeScript)
└── supabase/
    └── migrations/           # Supabase SQL migrations (schema + RLS)
```

- **`valuation_engine`** is the only place numerical valuation logic exists. It exposes `calculate(inputs) -> result` and an `excel.parse` / `excel.render` submodule. No HTTP, no DB. Released independently with a semver version tag.
- **`api`** is the only thing that talks to Supabase. It verifies Supabase JWTs, exposes the REST surface in §7, and writes audit-log rows in the same transaction as any change. It imports `valuation_engine` directly.
- **`web`** uses the Supabase JS client only for OAuth / session management. All data reads and writes go through the FastAPI service. The browser never holds the Supabase service-role key.
- **External pipeline** (out of scope for this repo) installs `valuation-engine` from a git tag and uses it as a library — no network hop.

Hosting target: Render (Web Service for API, Static Site for web), Supabase managed.

## 5. Data model (Supabase / Postgres)

```
entity                      -- legal owner: Trust, CC, Pty Ltd, etc.
  id, name, registration_number, notes, created_at, updated_at,
  deleted_at (soft delete)

property                    -- a building / asset owned by an entity
  id, entity_id (fk), name, address,
  property_type (office|retail|industrial|mixed|residential|other),
  notes, created_at, updated_at, deleted_at

valuation_snapshot          -- IMMUTABLE; one per save
  id, property_id (fk), valuation_date, created_by (auth.uid),
  created_at, status (active|superseded),
  inputs_json   (full ValuationInput, frozen)
  result_json   (full ValuationResult, frozen)
  market_value  (numeric, denormalised for fast portfolio queries)
  cap_rate      (numeric, denormalised)
  engine_version (text, semver of the engine that produced it)
  source        (manual|excel_import)
  source_file   (text, original filename if excel_import)

import_batch                -- one Excel batch run
  id, uploaded_by, uploaded_at, file_count,
  status (parsing|review|committed|cancelled), notes

import_item                 -- one file inside a batch
  id, batch_id (fk), filename, parse_status (ok|warning|error),
  parsed_inputs_json, computed_result_json,
  spreadsheet_market_value, recomputed_market_value, diff_pct,
  warnings_json, errors_json,
  resolution (pending|accepted|rejected|edited),
  resolved_property_id (fk, nullable),
  resolved_snapshot_id (fk, nullable)

app_user                    -- mirror of auth.users with role
  id (= auth.uid), email, display_name,
  role (valuer|viewer),
  created_at, last_seen_at

audit_log                   -- who did what, when
  id, actor_id, actor_email, action, target_table, target_id,
  before_json, after_json, created_at
```

Key choices:

- `valuation_snapshot` is the only place numbers live. `inputs_json` and `result_json` are JSONB so the engine schema can evolve without DB migrations; `market_value` and `cap_rate` are denormalised columns for portfolio queries.
- Snapshots are never updated or deleted. Corrections create a new snapshot; the old one stays for audit. The "current" valuation per property is `MAX(valuation_date) WHERE status = 'active'`.
- `engine_version` on every snapshot lets the system detect drift if the engine changes.
- Deletes on `entity` and `property` are soft (`deleted_at`); only allowed when no live children exist.
- Supabase RLS: all tables require `authenticated`. `viewer` gets `SELECT` only. `valuer` gets `SELECT + INSERT + UPDATE` on `entity` and `property`, and `INSERT` on `valuation_snapshot`, `import_batch`, `import_item`. `audit_log` is `INSERT`-only by the API service role; users can `SELECT`.
- Audit-log writes happen in the API layer, transactional with the change — not via DB triggers — so the source of audit truth lives in code.

## 6. Calculation engine (`valuation_engine`)

### 6.1 Package shape

```
valuation_engine/
├── __init__.py              # exposes calculate(), __version__
├── models.py                # Pydantic models
├── calculate.py             # pure core function
├── escalation.py            # rent-forward calc per tenant
├── warnings.py              # warning codes + descriptions
├── excel/
│   ├── parse.py             # openpyxl -> ValuationInput
│   └── render.py            # input + result -> openpyxl workbook
└── tests/
    ├── test_calculate.py
    ├── test_escalation.py
    └── golden/              # one input.json + expected.json per sample sheet
```

### 6.2 Public API

```python
def calculate(inputs: ValuationInput) -> ValuationResult: ...
__version__ = "0.1.0"
```

### 6.3 Models (Pydantic v2)

```python
class TenantLine(BaseModel):
    description: str
    tenant_name: str | None
    rentable_area_m2: Decimal              # > 0
    rent_per_m2_pm: Decimal                # current rent
    annual_escalation_pct: Decimal         # 0.08 = 8%; 0 if N/A
    next_escalation_date: date | None      # None => no escalation applied
    lease_period_text: str | None          # free text, audit only
    lease_expiry_date: date | None         # warning if before valuation_date

class ParkingLine(BaseModel):
    bay_type: Literal["open","covered","shade","basement","other"]
    bays: int
    rate_per_bay_pm: Decimal

class ValuationInput(BaseModel):
    valuation_date: date
    tenants: list[TenantLine]              # >= 1
    parking: list[ParkingLine] = []
    monthly_operating_expenses: Decimal    # total R/month
    vacancy_allowance_pct: Decimal         # 0.05 = 5%
    cap_rate: Decimal                      # > 0, e.g. 0.115
    rounding: Literal["nearest_10000","nearest_1000","none"] = "nearest_10000"

class ResolvedTenant(BaseModel):
    description: str
    rentable_area_m2: Decimal
    effective_rent_per_m2_pm: Decimal      # after escalation at valuation_date
    monthly_rent: Decimal
    escalation_cycles_applied: int

class Warning(BaseModel):
    code: str
    message: str
    field_path: str | None

class ValuationResult(BaseModel):
    engine_version: str
    valuation_date: date
    tenants_resolved: list[ResolvedTenant]
    gross_monthly_rent_tenants: Decimal
    gross_monthly_rent_parking: Decimal
    gross_monthly_income: Decimal
    gross_annual_income: Decimal
    annual_operating_expenses: Decimal
    opex_per_m2_pm: Decimal
    opex_pct_of_gai: Decimal
    vacancy_allowance_amount: Decimal
    annual_net_income: Decimal
    capitalised_value: Decimal             # ANI / cap_rate
    market_value: Decimal                  # rounded
    warnings: list[Warning]
```

### 6.4 Escalation rule (per tenant)

```
if next_escalation_date is None or valuation_date < next_escalation_date:
    rent = rent_per_m2_pm
else:
    cycles = floor((valuation_date - next_escalation_date).days / 365.25) + 1
    rent = rent_per_m2_pm * (1 + annual_escalation_pct) ** cycles
```

The engine capitalises the rent applicable on `valuation_date` only — no within-year averaging across an escalation step.

### 6.5 Validation

Hard errors (raise `ValueError`):

- `cap_rate <= 0`
- `tenants` empty
- any `rentable_area_m2 <= 0`
- any `rate_per_bay_pm < 0` or `bays < 0`
- `vacancy_allowance_pct < 0` or `> 1`

Warnings (returned in `result.warnings`, never raised):

| code | trigger |
|---|---|
| `lease_expired` | `lease_expiry_date < valuation_date` |
| `escalation_missing` | `annual_escalation_pct > 0` and `next_escalation_date is None` |
| `vacancy_zero` | `vacancy_allowance_pct == 0` |
| `opex_zero` | `monthly_operating_expenses == 0` |
| `opex_unusual_pct` | opex > 60% or < 5% of GAI |
| `cap_rate_unusual` | `cap_rate < 0.06` or `> 0.20` |
| `rent_unusual` | any tenant `rent_per_m2_pm < 20` or `> 1000` |

### 6.6 Numeric precision

All money/rates use `Decimal`. Rounding only at the final `market_value` step (per `rounding` policy). JSON serialisation emits `Decimal` as a string to preserve precision.

### 6.7 Testing

- Unit tests for `calculate.py` and `escalation.py`.
- Golden-value regression tests: one `inputs.json` + `expected_result.json` per sample workbook in `1. VALUATION EXAMPLES/`. CI fails on any drift.
- Round-trip excel test: `parse → calculate → render → parse → calculate` returns equal `ValuationResult`s.

## 7. FastAPI service

### 7.1 Auth

Every request carries `Authorization: Bearer <supabase JWT>`. Middleware verifies the JWT against Supabase JWKS, loads the `app_user` record, attaches `request.state.user`. `viewer` role returns 403 on any non-GET endpoint.

The API uses the Supabase service-role key for DB access (server-side only; never sent to the browser).

### 7.2 Endpoints

```
GET    /me

GET    /entities
POST   /entities
GET    /entities/{id}
PATCH  /entities/{id}
DELETE /entities/{id}                 -- soft delete; rejected if children exist

GET    /properties
POST   /properties
GET    /properties/{id}
PATCH  /properties/{id}
DELETE /properties/{id}

GET    /properties/{id}/snapshots
GET    /snapshots/{id}
POST   /properties/{id}/snapshots     -- body = ValuationInput; persists
POST   /calculate                     -- body = ValuationInput; preview, no DB write

POST   /imports                       -- multipart .xlsx upload; returns batch_id
GET    /imports/{batch_id}
PATCH  /imports/{batch_id}/items/{id}
POST   /imports/{batch_id}/commit

GET    /snapshots/{id}/export.pdf
GET    /snapshots/{id}/export.xlsx

GET    /portfolio/summary
GET    /portfolio/timeseries

GET    /users
GET    /audit
```

### 7.3 Background work

Excel parsing for a batch runs via FastAPI `BackgroundTasks` (in-process) for v1. If batch sizes grow, swap to a Render background worker — the API surface does not change.

### 7.4 Errors

Consistent envelope: `{"error": {"code": "...", "message": "...", "details": {...}}}`. Engine `ValueError` → 422; Pydantic validation → 422; auth failure → 401/403; not-found → 404.

### 7.5 Engine version recording

API does `from valuation_engine import calculate, __version__` at module import; every `valuation_snapshot` row writes `engine_version=__version__`. The pipeline does the same.

## 8. React web app

### 8.1 Stack

Vite + React + TypeScript + Tailwind + shadcn/ui + TanStack Query + React Router + react-hook-form + zod.

Auth: Supabase JS client handles OAuth (Google / Microsoft); session token sent on every API request via TanStack Query's default fetcher. No direct Supabase DB access from the browser.

### 8.2 Routes

```
/login                       OAuth (Google / Microsoft)
/                            Portfolio dashboard
/entities                    List + create entity
/entities/:id                Entity detail (properties owned)
/properties                  List with filter / search
/properties/new
/properties/:id              Property detail — latest snapshot, history list
/properties/:id/valuations/new       Valuation editor (manual entry)
/properties/:id/valuations/:sid      Snapshot viewer + Export PDF / XLSX
/imports                     Import batches list
/imports/new                 Drop .xlsx files, kick off batch
/imports/:id                 Review queue
/audit
/settings/users              View users + role (read-only in v1)
```

### 8.3 Key pages

**Valuation editor.** Three sections mirroring the spreadsheet — Tenants, Parking, Assumptions. Right-rail live result calls `POST /calculate` debounced 300ms; warnings render inline next to offending fields. "Save snapshot" posts to `POST /properties/:id/snapshots` and routes to the snapshot viewer.

**Snapshot viewer.** Read-only render of inputs + result + warnings + engine version + author + timestamp. "Export PDF" / "Export XLSX" buttons. "New valuation from this" pre-fills the editor — revaluation is edit + save.

**Import review.** Table of files per batch with parsed entity / property, sheet value, recomputed value, diff %, status, resolution. Side panel lets the user edit parsed inputs, accept / reject / edit-and-accept, and link or create the entity/property. "Commit batch" enabled when no row is `pending`; rows that fail to commit stay `pending` for re-resolution.

**Portfolio dashboard.** KPI cards (total value, # properties, # entities, last snapshot date), charts (value-by-type donut, value-by-entity bar, portfolio value over time line), top-N properties table. Viewer role hides create/edit affordances.

### 8.4 Component organisation

```
src/
├── lib/                     api client, auth, query setup
├── schemas/                 zod schemas mirroring Pydantic
├── components/ui/           shadcn primitives
├── components/valuation/    TenantRow, ParkingRow, ResultPanel, WarningChip
├── components/import/       ImportItemTable, ImportItemPanel
├── pages/
└── routes.tsx
```

## 9. Excel I/O

### 9.1 Canonical layout (from sample sheets)

Single sheet per workbook:

```
Row 1   A: "Building name :"        B: <name>
Row 2   A: "Date"                   E: <valuation_date>
Row 3   header: Tenant | Description | Annual escalation | Lease period |
                Lease expiry date | Rentable area | R/m²/pm | Opex R/m²/pm |
                Gross monthly rent
Rows 4..N    tenant rows (I = G * F)
Row N+1      "Sub total"            F = SUM(area)   I = SUM(rent)
Row N+3      "Parking"              F: "No. bays"   G: "R/bay"
Rows N+4..M  parking rows (E type, F bays, G rate, I = G * F)
Row M+1      "Sub total"
Row M+2      "Gross monthly income" I = parking_sub + tenant_sub
Row M+3      "Gross annual income"  I = prev * 12
Row M+4      "Operating expenses"   headers: Monthly | Annual | R/m²/pm | %GAI
Row M+5      "Sub total"            E = monthly  F = E * 12  G = E / area  H = F / GAI
Row M+6      "Vacancy allowance"    H = pct      I = GAI * -H
Row M+7      "Monthly net income"   I = ANI / 12
Row M+8      "Annual net income"    I = GAI - annual_opex + vacancy
Row M+9      "Capitalised @"        H = cap_rate I = ANI / H
Row M+10     "Open market assessment" I = ROUND(prev, -4)
```

### 9.2 Parser (tolerant, label-driven)

Does not rely on absolute row numbers. Walks the sheet using column-A label anchors:

1. Find `Building name` → `building_name` (col B); `Date` → `valuation_date` (col E).
2. Find header row containing `Rentable area` — start of tenant rows.
3. Read tenant rows downward until column A is `Sub total` or empty for >= 2 rows.
4. Find `Parking` → header row below it → read parking rows until `Sub total`.
5. Find `Operating expenses` → next `Sub total` row → monthly opex from col E.
6. Find `Vacancy allowance` → vacancy % from col H.
7. Find `Capitalised @` → cap rate from col H, sheet-stored value from col I (for compare).
8. Find `Open market assessment` → sheet-stored final value (for compare).

For the recompute-and-compare check, parser uses `data_only=True` to read cached formula values, then re-runs the engine and computes `diff_pct = abs(recomputed - sheet) / sheet`. Threshold: `diff_pct > 0.001` (0.1%) flags the item with the `recompute_mismatch` warning so the reviewer must explicitly accept or edit before commit. Tolerance below that is treated as rounding noise.

Returns `ParseResult { inputs, building_name, sheet_market_value, parse_warnings }`.

### 9.3 Parse warnings (separate from engine warnings)

| code | severity | trigger |
|---|---|---|
| `unrecognised_row` | warning | non-empty row in a section that didn't match any expected pattern |
| `missing_optional_section` | warning | Parking section absent (defaults to no parking lines) |
| `missing_required_section` | error | Tenants, Opex, Vacancy, or Cap rate section absent — item cannot be parsed; resolution must be `rejected` or `edited` |
| `multiple_sheets` | warning | workbook has >1 sheet (only the first is used) |
| `non_canonical_label` | warning | label drift, e.g. "Gross income" instead of "Gross monthly income" |
| `formula_missing_value` | warning | formula cell has no cached value (workbook never opened in Excel after edit); falls back to recomputing inputs only |
| `recompute_mismatch` | warning | engine result differs from sheet's stored market value by `diff_pct > 0.001` |

Errors set the item's `parse_status = error` and require an editor to fix before commit; warnings set `parse_status = warning` and allow accept-without-edit.

### 9.4 Renderer

Takes `ValuationInput + ValuationResult` and writes a workbook in the canonical layout above, preserving formulas (not just values) so a recipient can audit the math in Excel.

### 9.5 Round-trip golden test

For every sample .xlsx in CI: `parse → calculate → render → parse → calculate` and assert the two `ValuationResult`s are equal.

### 9.6 Batch flow

`POST /imports` writes uploaded files to a temp location and starts a background task that parses each, runs the engine, writes `import_item` rows with diffs and warnings; batch status flips `parsing → review`. The user reviews in the UI, sets resolutions, then `POST /imports/{id}/commit` creates entity/property/snapshot rows atomically per item — a single failing row stays `pending` rather than rolling back the batch.

## 10. PDF export

Server-side rendering with **WeasyPrint**: HTML/CSS in, PDF out, no headless browser, no extra service. Render's Python image needs Pango/Cairo system libs (one-line in the Render build command).

```
packages/api/app/exports/
├── pdf_template.html        # Jinja2 template
├── pdf_styles.css           # print-targeted, A4 page, monospace numbers
└── pdf.py                   # render_snapshot_pdf(snapshot) -> bytes
```

Endpoint `GET /snapshots/{id}/export.pdf` loads the snapshot and returns `application/pdf` with `Content-Disposition: attachment; filename=<entity>_<property>_<date>.pdf`.

Single canonical template in v1. Branding (logo, firm details) comes from a small `settings` table or env vars so the template stays static.

## 11. Hosting, CI, packaging

### 11.1 Render

- **`api`** — Web Service, Python. Build: `pip install -e ../valuation_engine && pip install -r requirements.txt`. Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Env: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `ALLOWED_ORIGINS`.
- **`web`** — Static Site. Build: `npm ci && npm run build`; publish: `dist/`. Build-time env: `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`.
- **Supabase** — managed; migrations in `supabase/migrations/` applied via the Supabase CLI from CI (or hand-applied for v1).

### 11.2 Engine packaging

`packages/valuation_engine/pyproject.toml` declares `name = "valuation-engine"`, `version` from `__version__`, `build-backend = "hatchling"`.

Versioned releases via git tags (`v0.1.0`, `v0.2.0`, ...). The pipeline installs the engine with:

```
pip install \
  git+https://github.com/henrye1/property-valuation-model.git@v0.1.0#subdirectory=packages/valuation_engine
```

GitHub repo: `henrye1/property-valuation-model` (note: repo name is `property-valuation-model` singular, local folder is `property-valuations-model` plural — kept distinct intentionally; no rename required). No private PyPI required for v1.

Within the monorepo, `api` depends on the engine via path (`valuation-engine @ file:../valuation_engine`) in dev; CI swaps to the tagged version on release.

**Semver discipline.** Any change to `ValuationInput`/`ValuationResult` shape or any change that alters a numeric output bumps **minor** (additive) or **major** (breaking). Pure refactors are **patch**. Every snapshot stores `engine_version`, so historical valuations remain interpretable forever.

### 11.3 CI (GitHub Actions)

1. **Engine job** — ruff, mypy, unit tests, golden tests across all sample sheets, round-trip parse/render/parse equality.
2. **API job** — ruff, mypy, pytest with a Supabase test project (or Postgres + pgTAP) — covers auth middleware, endpoint contracts, audit-log writes.
3. **Web job** — eslint, tsc, Vitest unit tests, Playwright smoke against staging.
4. **Release job** (tag-triggered) — runs the above, deploys to Render via deploy hooks.

### 11.4 Local dev

- `docker compose up` for Supabase local (postgres + auth + storage).
- `uv` for Python env management; `pnpm` for the web workspace.
- `make dev` starts engine (editable), API on `:8000`, web on `:5173`, Supabase on `:54321`.

### 11.5 Observability (v1)

- API: structured JSON logs to stdout, Sentry for errors, `GET /healthz` for Render health checks.
- Web: Sentry browser SDK.

## 12. Open items deferred to later versions

- Admin role + in-app user/role management.
- Multi-tenant (per-organisation) data isolation.
- VAT-aware rent inputs.
- Forward-looking valuations using a 12-month-average or DCF approach.
- File attachments per property.
- Scheduled / emailed reports.
- Custom user-defined property fields.

## 13. Decisions log

| # | Decision |
|---|---|
| Q1 | Single-property calculator + Excel import/export + portfolio reporting + roles. |
| Q2 | Single-tenant; two roles (Valuer, Viewer). |
| Q3 | Immutable dated snapshots; latest = current; full history viewable. |
| Q4 | Manual UI entry primary; Excel import optional batch with tolerant parsing + recompute-and-compare + review queue. |
| Q5 | Engine = library + FastAPI; pipeline imports the package directly. |
| Q6 | Entity → Property → Snapshot data model. |
| Q7 | Supabase auth via Google / Microsoft OAuth. |
| Q8 | In-app dashboard + per-property PDF + Excel round-trip export. |
| Q9 | Render hosting (FastAPI Web Service + React Static Site); Supabase managed; engine published as a versioned package. |
| Q10 | Engine strict on hard errors; warnings list for soft data-quality issues. |
| Q11 | ZAR single currency; audit log included. |
| Q11.1 | Engine takes `valuation_date`; per-tenant `next_escalation_date` + `escalation %`; rent compounds on each anniversary of `next_escalation_date` until `valuation_date`. |
| §6.4 | Engine capitalises rent applicable on `valuation_date` (no within-year averaging across an escalation step). |
| §4 | Monorepo, three packages (Option 1). |
| §10 | WeasyPrint for PDF rendering. |
