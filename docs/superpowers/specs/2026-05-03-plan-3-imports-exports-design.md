# Plan 3 — Excel Imports + PDF/XLSX Exports — Design

**Date:** 2026-05-03
**Status:** Approved (brainstorming)
**Author:** Henry (henry@anchorpointrisk.co.za)
**Branch:** `plan-3-imports-exports` (off `main` at `606edbe`)
**Top-level spec reference:** [`docs/superpowers/specs/2026-04-23-property-valuations-model-design.md`](./2026-04-23-property-valuations-model-design.md)
**Plan 2 reference:** [`docs/superpowers/specs/2026-04-24-api-core-design.md`](./2026-04-24-api-core-design.md)

## 1. Purpose

Add the bulk-import workflow and the per-snapshot export endpoints to the FastAPI service shipped in Plan 2. Specifically:

- Upload one or more `.xlsx` workbooks → background parse → reviewer queue → per-item commit that creates `valuation_snapshot` rows under existing entities/properties.
- `GET /snapshots/{id}/export.pdf` — single-page valuation report rendered server-side via WeasyPrint.
- `GET /snapshots/{id}/export.xlsx` — canonical workbook rendered fresh from the snapshot via `valuation_engine.excel.render`.

This plan is **pure API plumbing**: the engine's `excel.parse` and `excel.render` already shipped in Plan 1, so no engine work is required. No web UI in this plan (deferred to Plan 4).

## 2. Goals

- Onboard the ~130 historical Excel workbooks with reviewer oversight.
- Surface every snapshot as a print-ready PDF and as a re-openable XLSX.
- Reuse the Plan 2 audit, error-envelope, JWT, and role-gate machinery — no new patterns invented.
- Production-ready Render deploy with one-line apt-install for WeasyPrint dependencies.

## 3. Non-goals (this plan)

- Inline entity / property creation inside the commit endpoint (reviewer must use Plan 2 endpoints first; see §10.3).
- Aggressive parser recovery for non-canonical layouts — strict canonical only.
- Pixel-fidelity branded report cover pages or methodology copy (deferred to a future Plan 5 styling pass).
- Bulk PDF/XLSX export (one snapshot per request).
- Storage-side caching of rendered exports (HTTP `Cache-Control: immutable` is sufficient at v1 traffic).
- Concurrent-commit race protection beyond the per-item idempotency.
- Web UI (Plan 4).

## 4. Decisions log (Q1–Q15)

| # | Decision |
|---|---|
| Q1 | Merge `plan-2-api-core` to `main` first (done — `606edbe`). |
| Q2 | Plan 3 next (imports + exports) before Plan 4 (web UI). |
| Q2.1 | Fold Plan 2 carry-overs (db.py timeout, errors.py narrowing) into start of Plan 3 branch. |
| Q3 | Strict canonical parser — anything not closely matching the canonical layout → `parse_status='error'`, reviewer must edit or reject. |
| Q4 | Cut `plan-3-imports-exports` off `main` immediately; spec, plan, and implementation all live there. |
| Q5 | Uploaded workbooks live in a private Supabase Storage bucket (`imports`); auto-deleted on batch terminal state. |
| Q6 | Auto-suggest entity/property by exact + fuzzy match on `building_name`. |
| Q7 | Per-item commit transactions; `POST /imports/{id}/commit` is idempotent. |
| Q8 | WeasyPrint shipped via apt-install in Render's build command (Dockerfile updated as future fallback). |
| Q9 | PDF: canonical Excel-layout body + valuation-summary header + warnings/metadata footer. |
| Q10 | XLSX: always render fresh from the snapshot via `valuation_engine.excel.render`. |
| Q11 | Engine `excel.parse` + `excel.render` confirmed shipped in Plan 1 — Plan 3 is pure API plumbing. |
| Q12 | Original-workbook download via 5-minute Supabase Storage signed URL (307 redirect from API). |
| Q13a | `pg_trgm` similarity, threshold 0.5, scoped to `property` table (single-tenant). |
| Q13b | Exact-name match auto-links to existing property and inherits its `entity_id` silently. |
| Q14 | Ignore concurrent-commit races; per-item idempotency covers correctness. |
| Q15 | PDF/XLSX caching via HTTP headers only (`Cache-Control: public, max-age=31536000, immutable` + ETag = `snapshot.id`). |

## 5. Architecture

Plan 3 adds **one new subsystem** to `packages/api/` (the import pipeline) and **two new endpoints** (PDF/XLSX export). No new packages, no new services.

```
packages/api/src/api/
├── routers/
│   ├── imports.py            # NEW
│   └── exports.py            # NEW
├── queries/
│   ├── import_batch.py       # NEW
│   └── import_item.py        # NEW
├── schemas/
│   └── imports.py            # NEW
├── services/                 # NEW DIRECTORY
│   ├── __init__.py
│   ├── storage.py            # Supabase Storage wrapper
│   ├── parse_worker.py       # background-task entry point
│   ├── matcher.py            # pg_trgm-backed property suggestions
│   ├── commit_worker.py      # idempotent per-item commit loop
│   └── exports.py            # WeasyPrint PDF rendering
├── exports/                  # NEW DIRECTORY (template assets)
│   ├── pdf_template.html
│   └── pdf_styles.css
├── branding/                 # NEW DIRECTORY (firm logo)
│   ├── README.md
│   └── anchorpoint_logo.png
└── (everything else unchanged)

supabase/migrations/
├── 20260503000001_carryovers.sql        # NEW (no schema change; placeholder for any DDL the carry-overs need)
├── 20260503000002_pg_trgm.sql           # NEW — CREATE EXTENSION + GIN index on property.name
├── 20260503000003_import_batch.sql      # NEW
├── 20260503000004_import_item.sql       # NEW
├── 20260503000005_imports_rls.sql       # NEW
└── 20260503000006_storage_bucket.sql    # NEW — private bucket + retention rules
```

### 5.1 Module boundaries (the contract)

- **`routers/imports.py`** owns HTTP only: parse multipart, return DTOs, dispatch background tasks. No SQL, no Storage SDK calls, no parsing.
- **`services/storage.py`** is the only file that imports the Supabase Storage SDK. Exposes `upload(batch_id, filename, bytes) -> path`, `download(path) -> bytes`, `signed_url(path) -> str`, `delete_prefix(batch_id)`.
- **`services/parse_worker.py`** is the FastAPI `BackgroundTasks` entry point. Pulls each file from Storage, runs `valuation_engine.excel.parse`, runs `valuation_engine.calculate`, calls `matcher.suggest`, writes one `import_item` row. Catches all exceptions per file → row-level `parse_status='error'`.
- **`services/matcher.py`** exposes `suggest(building_name) -> MatchResult`. Pure SQL against `pg_trgm`. Threshold and result count are module-level constants.
- **`services/commit_worker.py`** is invoked synchronously by `POST /imports/{id}/commit`. Loops items in `(pending|accepted|edited)` with `resolved_snapshot_id IS NULL`, opens one transaction per item, returns a `{committed, failed, skipped}` summary. Idempotent.
- **`services/exports.py`** owns WeasyPrint rendering. The XLSX export is a one-liner in `routers/exports.py` (calls `valuation_engine.excel.render`); the PDF needs its own module because of template loading and number formatting.

### 5.2 Data flow

```
Upload
  reviewer  ──multipart──▶ POST /imports ──▶ storage.upload(...) ──▶ parse_worker (BackgroundTasks)
                                                                              │
                                                                              ▼
                                                          import_batch + N×import_item rows

Review
  reviewer  ──GET──▶ /imports/{id}                                ──▶ batch + items + suggestions
  reviewer  ──GET──▶ /imports/{id}/items/{id}/source              ──▶ 307 redirect to Storage signed URL
  reviewer  ──PATCH──▶ /imports/{id}/items/{id}                   ──▶ resolution + linked property + edited inputs

Commit
  reviewer  ──POST──▶ /imports/{id}/commit ──▶ commit_worker
                                                  │
                                                  ▼
              for each pending|accepted|edited item:
                  BEGIN; insert snapshot (with supersede); audit; COMMIT
                                                  │
                                                  ▼
              storage.delete_prefix(batch_id) when batch reaches terminal state

Export
  reviewer  ──GET──▶ /snapshots/{id}/export.pdf  ──▶ exports.render_snapshot_pdf(snapshot) ──▶ application/pdf
  reviewer  ──GET──▶ /snapshots/{id}/export.xlsx ──▶ engine.excel.render(snapshot)         ──▶ application/vnd.openxmlformats...
                                            (both with Cache-Control: immutable + ETag = snapshot.id)
```

### 5.3 What does NOT change

- `auth.py`, `db.py`, `errors.py`, `audit.py` — **carry-over fixes only** (pool acquire timeout, narrowed `ValueError` handler), no architectural changes.
- All existing routers/queries/schemas — untouched.
- The valuation engine — untouched.
- The Render web service definition — only the build command changes (apt-install Pango/Cairo).

## 6. Data model

### 6.1 `import_batch`

```sql
create table import_batch (
  id            uuid primary key default gen_random_uuid(),
  uploaded_by   uuid not null references app_user(id),
  uploaded_at   timestamptz not null default now(),
  file_count    int  not null check (file_count >= 1),
  status        text not null check (status in ('parsing','review','committed','cancelled')),
  notes         text
);

create index import_batch_uploaded_by_idx on import_batch (uploaded_by, uploaded_at desc);
```

Status transitions:

```
parsing ──▶ review ──▶ committed
                  └──▶ cancelled
```

Terminal states (`committed`, `cancelled`) trigger `storage.delete_prefix(batch_id)`. Rows are never deleted.

### 6.2 `import_item`

```sql
create table import_item (
  id                       uuid primary key default gen_random_uuid(),
  batch_id                 uuid not null references import_batch(id) on delete cascade,
  filename                 text not null,
  storage_path             text not null,                -- 'imports/<batch_id>/<safe_filename>'

  -- Parser output
  parse_status             text not null check (parse_status in ('ok','warning','error')),
  building_name            text,
  parsed_inputs_json       jsonb,                        -- ValuationInput, null on hard parse error
  computed_result_json     jsonb,                        -- engine output for parsed_inputs
  spreadsheet_market_value numeric,
  recomputed_market_value  numeric,
  diff_pct                 numeric,
  warnings_json            jsonb not null default '[]'::jsonb,
  errors_json              jsonb not null default '[]'::jsonb,

  -- Auto-suggest (set by parse_worker)
  suggested_property_id    uuid references property(id),
  suggested_score          numeric,
  auto_linked              boolean not null default false,

  -- Reviewer resolution
  resolution               text not null default 'pending'
                                check (resolution in ('pending','accepted','rejected','edited','committed')),
  resolved_property_id     uuid references property(id),
  resolved_snapshot_id     uuid references valuation_snapshot(id),
  resolved_inputs_json     jsonb,                        -- post-edit inputs; null if reviewer didn't edit
  resolution_notes         text,
  resolved_at              timestamptz,
  resolved_by              uuid references app_user(id),

  created_at               timestamptz not null default now()
);

create index import_item_batch_idx       on import_item (batch_id);
create index import_item_resolution_idx  on import_item (batch_id, resolution);
```

Notes:
- `errors_json` is non-empty iff `parse_status='error'`. Items with errors can only resolve to `rejected` or `edited`.
- `resolved_inputs_json` is what gets written to `valuation_snapshot.inputs_json` at commit time. If null, falls back to `parsed_inputs_json`.
- `suggested_*` columns are populated once at parse time. The matcher does not re-run at commit time.

### 6.3 `pg_trgm` extension + index

```sql
create extension if not exists pg_trgm;

create index property_name_trgm_idx on property using gin (name gin_trgm_ops)
  where deleted_at is null;
```

The partial index keeps the matcher from suggesting soft-deleted properties.

### 6.4 RLS policies

```sql
alter table import_batch enable row level security;
alter table import_item  enable row level security;

-- Viewer + Valuer can read all batches/items
create policy import_batch_select on import_batch for select to authenticated using (true);
create policy import_item_select  on import_item  for select to authenticated using (true);

-- Only valuers create/update batches; uploaded_by must be auth.uid() on insert
create policy import_batch_insert on import_batch
  for insert to authenticated
  with check (
    exists (select 1 from app_user u where u.id = auth.uid() and u.role = 'valuer')
    and uploaded_by = auth.uid()
  );

create policy import_batch_update on import_batch
  for update to authenticated
  using (exists (select 1 from app_user u where u.id = auth.uid() and u.role = 'valuer'));

create policy import_item_insert on import_item for insert to authenticated
  with check (exists (select 1 from app_user u where u.id = auth.uid() and u.role = 'valuer'));

create policy import_item_update on import_item for update to authenticated
  using (exists (select 1 from app_user u where u.id = auth.uid() and u.role = 'valuer'));

-- No DELETE policy on either; rows are kept for audit.
```

The API uses the service-role key (bypasses RLS); policies are defence-in-depth, matching the Plan 2 pattern.

### 6.5 Supabase Storage bucket

```sql
insert into storage.buckets (id, name, public)
values ('imports', 'imports', false)
on conflict (id) do nothing;

-- No public read policy. All access through the API; service-role credentials
-- mint 5-minute signed URLs on demand.
```

Bucket layout:

```
imports/
└── <batch_id>/
    ├── <filename1>.xlsx
    ├── <filename2>.xlsx
    └── ...
```

Filename collisions within a batch are resolved by appending `__1`, `__2`, ... to `storage_path`; the original `filename` column preserves the user-visible name.

### 6.6 Audit-log entries written by Plan 3

Same `audit()` helper from Plan 2; same envelope.

| Action | Target | `after_json` |
|---|---|---|
| `import_batch.create` | `import_batch.id` | `{file_count, filenames}` |
| `import_batch.cancel` | `import_batch.id` | `{}` |
| `import_item.update` | `import_item.id` | full new row state |
| `import_batch.commit` | `import_batch.id` | `{committed, failed, skipped, batch_status}` |
| `valuation_snapshot.create` | `valuation_snapshot.id` | `{property_id, valuation_date, market_value, source: 'excel_import', source_file, import_item_id}` |

## 7. Endpoints

JWT auth + valuer role enforced unless noted. Error envelope `{"error": {...}}` matches Plan 2.

### 7.1 Endpoint summary table

| Method | Path | Role | Status codes |
|---|---|---|---|
| `POST` | `/imports` | valuer | 202, 400, 401, 403, 413 |
| `GET` | `/imports` | both | 200, 401 |
| `GET` | `/imports/{id}` | both | 200, 401, 404 |
| `PATCH` | `/imports/{id}/items/{iid}` | valuer | 200, 401, 403, 404, 409, 422 |
| `POST` | `/imports/{id}/cancel` | valuer | 200, 401, 403, 404, 409 |
| `POST` | `/imports/{id}/commit` | valuer | 200, 401, 403, 404, 409 |
| `GET` | `/imports/{id}/items/{iid}/source` | both | 307, 401, 404, 410 |
| `GET` | `/snapshots/{id}/export.pdf` | both | 200, 304, 401, 404 |
| `GET` | `/snapshots/{id}/export.xlsx` | both | 200, 304, 401, 404 |

### 7.2 `POST /imports`

Multipart upload. Body: one or more `.xlsx` files in field `files`.

```
Response: 202 Accepted
{ "batch_id": "uuid", "file_count": 12, "status": "parsing" }
```

Validation:
1. `len(files) == 0` → 400 `no_files`.
2. Any file > `IMPORT_MAX_FILE_BYTES` (default 10 MB) → 413 `file_too_large`.
3. Any non-`.xlsx` extension (case-insensitive) → 400 `unsupported_file_type`.
4. No total-batch size cap in v1; Render's request body limit is the practical ceiling.

Behaviour:
1. Upload each file to Storage with `__N` suffix on filename collision.
2. Insert `import_batch` (`status='parsing'`) and one placeholder `import_item` per file.
3. Schedule `parse_worker.run(batch_id)` via `BackgroundTasks`.
4. Return 202 with `batch_id`.

### 7.3 `GET /imports`

```
Query:    ?status=parsing|review|committed|cancelled (optional, repeatable)
          ?limit=50  ?offset=0   (default 50/0, max 200)
Response: 200
{
  "items": [
    {
      "id": "uuid",
      "uploaded_by": {"id": "uuid", "email": "..."},
      "uploaded_at": "2026-05-03T12:34:56Z",
      "file_count": 12,
      "status": "review",
      "counts": {"pending": 3, "accepted": 8, "rejected": 1, "committed": 0}
    }, ...
  ],
  "total": 47
}
```

Per-status counts come from a single grouped query joined to the batch list — no N+1.

### 7.4 `GET /imports/{batch_id}`

Returns batch row + all items inline (no pagination on items in v1; max 130 per realistic batch).

```
Response: 200
{
  "id": "uuid",
  "uploaded_by": {...},
  "uploaded_at": "...",
  "file_count": 12,
  "status": "review",
  "notes": null,
  "items": [
    {
      "id": "uuid",
      "filename": "55 Empire Road.xlsx",
      "parse_status": "warning",
      "building_name": "55 Empire Road",
      "spreadsheet_market_value": "12500000.00",
      "recomputed_market_value": "12500000.00",
      "diff_pct": "0.0000",
      "warnings": [{"code": "lease_expired", "message": "...", "field_path": "tenants[2].lease_expiry_date"}],
      "errors": [],
      "suggestion": {
        "property_id": "uuid",
        "property_name": "55 Empire Road",
        "entity_id": "uuid",
        "entity_name": "Empire Road Trust",
        "score": 1.0,
        "auto_linked": true
      },
      "resolution": "accepted",
      "resolved_property_id": "uuid",
      "parsed_inputs": { ...ValuationInput... },
      "computed_result": { ...ValuationResult... },
      "resolved_inputs": null
    }
  ]
}
```

### 7.5 `PATCH /imports/{batch_id}/items/{item_id}`

Reviewer sets resolution and/or edits inputs. Rejected if `batch.status != 'review'` → 409 `batch_not_in_review`.

```
Request:
{
  "resolution": "accepted" | "rejected" | "edited",          // required
  "resolved_property_id": "uuid" | null,                     // required if accepted/edited and no auto-link
  "resolved_inputs": { ...ValuationInput... } | null,        // required iff resolution = "edited"
  "resolution_notes": "string" | null
}
Response: 200 — full updated item shape
```

Validation matrix:
- `resolution='rejected'` → `resolved_property_id` and `resolved_inputs` ignored if sent.
- `resolution='accepted'` requires either `auto_linked=true` already on the row OR an explicit `resolved_property_id`.
- `resolution='edited'` requires both `resolved_inputs` and `resolved_property_id`.
- `resolution='edited'` re-runs the engine server-side on the new inputs (raises 422 if hard validation fails) and stores the new `computed_result_json`.
- `parse_status='error'` items cannot resolve to `accepted` → 422 `error_item_must_be_edited_or_rejected`.
- Sets `resolved_at = now()`, `resolved_by = current_user.id`.
- Audit row: `import_item.update`.

### 7.6 `POST /imports/{batch_id}/cancel`

Rejected if `batch.status not in ('parsing','review')` → 409.

```
Response: 200 { "id": "uuid", "status": "cancelled" }
```

Side effects: `storage.delete_prefix(batch_id)`, audit row.

### 7.7 `POST /imports/{batch_id}/commit`

Rejected if `batch.status != 'review'` → 409.

```
Response: 200
{
  "batch_id": "uuid",
  "summary": {
    "committed": 8,
    "failed":    1,
    "skipped":   3   // already-committed items from a prior call
  },
  "failures": [
    {
      "item_id": "uuid",
      "filename": "...",
      "reason": "duplicate_snapshot_for_date",
      "message": "..."
    }
  ],
  "batch_status": "committed" | "review"
}
```

Behaviour: see §10. Idempotent — re-callable; `skipped` counts items with `resolved_snapshot_id IS NOT NULL`.

### 7.8 `GET /imports/{batch_id}/items/{item_id}/source`

```
Response: 307 Temporary Redirect
Location: <Supabase Storage signed URL, ttl=300s>
```

If the file no longer exists in Storage (batch in terminal state) → 410 `source_unavailable`.

### 7.9 `GET /snapshots/{id}/export.pdf`

```
Response: 200
Content-Type: application/pdf
Content-Disposition: attachment; filename="<entity>_<property>_<valuation_date>.pdf"
Cache-Control: public, max-age=31536000, immutable
ETag: "<snapshot.id>"
```

`If-None-Match` matching → 304 (skip render entirely).

### 7.10 `GET /snapshots/{id}/export.xlsx`

```
Response: 200
Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
Content-Disposition: attachment; filename="<entity>_<property>_<valuation_date>.xlsx"
Cache-Control: public, max-age=31536000, immutable
ETag: "<snapshot.id>"
```

`If-None-Match` matching → 304.

### 7.11 OpenAPI / Swagger

All new endpoints declared with the existing `bearerAuth` security scheme (Plan 2 commit `41b00d1`). Pydantic response models auto-document bodies.

## 8. Parser & background task

### 8.1 Trigger

`POST /imports` calls `BackgroundTasks.add_task(parse_worker.run, batch_id)` *after* the HTTP response is sent. The handler returns 202 in <100ms.

**One worker per batch, sequential per item.** Engine parse is ~50ms/workbook in Plan 1 tests; a 130-file batch completes in ~7s of CPU. Concurrent batches share the connection pool naturally.

### 8.2 Worker entry point

```python
async def run(batch_id: UUID) -> None:
    async with db.pool.acquire(timeout=10) as conn:
        items = await import_item_q.list_for_parsing(conn, batch_id)
        for item in items:
            try:
                await _process_one(conn, batch_id, item)
            except Exception as exc:                       # noqa: BLE001
                logger.exception("parse_worker_item_failed", item_id=str(item.id))
                await import_item_q.mark_unrecoverable_error(
                    conn, item.id, repr(exc)
                )
        await import_batch_q.set_status(conn, batch_id, "review")
```

The outer broad `except` is the **only place broad exception catch is permitted in this codebase**. A bad workbook must not poison the rest of the batch. Always logs full stack to Sentry; item gets `parse_status='error'`, `errors=[{code: 'unrecoverable_parse_error', message: <repr>}]`.

### 8.3 Per-item processing

```python
async def _process_one(conn, batch_id: UUID, item: ImportItemRow) -> None:
    # 1. Fetch bytes from Storage.
    raw = await storage.download(item.storage_path)

    # 2. Parse via engine. ParseResult or HardParseError.
    try:
        parsed = excel.parse(raw, filename=item.filename)
    except excel.HardParseError as e:
        await import_item_q.mark_parse_error(conn, item.id, errors=[e.to_dict()])
        return

    # 3. Recompute via the engine.
    try:
        result = engine.calculate(parsed.inputs)
    except ValueError as e:
        await import_item_q.mark_parse_error(
            conn, item.id,
            building_name=parsed.building_name,
            parsed_inputs_json=parsed.inputs.model_dump(),
            errors=[{"code": "engine_validation_error", "message": str(e)}],
        )
        return

    # 4. Compute diff_pct.
    diff_pct, diff_warning = _compute_diff(parsed.sheet_market_value, result.market_value)

    # 5. Aggregate warnings.
    all_warnings = (
        [w.model_dump() for w in result.warnings]
        + [w.to_dict() for w in parsed.parse_warnings]
        + ([diff_warning] if diff_warning else [])
    )

    # 6. Auto-suggest match.
    match = await matcher.suggest(conn, parsed.building_name)

    # 7. Persist.
    await import_item_q.mark_parsed(
        conn,
        item.id,
        building_name=parsed.building_name,
        parsed_inputs_json=parsed.inputs.model_dump(),
        computed_result_json=result.model_dump(),
        spreadsheet_market_value=parsed.sheet_market_value,
        recomputed_market_value=result.market_value,
        diff_pct=diff_pct,
        warnings_json=all_warnings,
        parse_status="warning" if all_warnings else "ok",
        suggested_property_id=match.property_id,
        suggested_score=match.score,
        auto_linked=match.auto_linked,
        resolution=("accepted" if match.auto_linked else "pending"),
        resolved_property_id=(match.property_id if match.auto_linked else None),
    )
```

Key behaviours:
- **Auto-link → auto-accept.** Exact name match on a single property → `resolution='accepted'` immediately. Reviewer only acts on outliers.
- **Auto-link does NOT auto-commit.** Auto-accepted items still wait for `POST .../commit`. Reviewer can flip back to `pending` or `rejected` via PATCH.
- **`diff_pct`:** if `parsed.sheet_market_value is None` → null + `formula_missing_value` warning. If `> 0.001` → `recompute_mismatch` warning, but `parse_status='warning'` not `'error'`.

### 8.4 Engine integration points

The engine (Plan 1) exposes:

- `valuation_engine.excel.parse(bytes, filename) -> ParseResult` with `.inputs`, `.building_name`, `.sheet_market_value`, `.parse_warnings`. Hard parse errors raised as `HardParseError`.
- `valuation_engine.calculate(inputs) -> ValuationResult`.
- `valuation_engine.excel.render(inputs, result) -> bytes`.

API wraps them in `services/exports.py` and `services/parse_worker.py`. **Zero re-implementation of engine logic in the API package.**

### 8.5 Matcher

```python
SIMILARITY_THRESHOLD = 0.5   # tunable; pg_trgm default is 0.3
MAX_SUGGESTIONS = 5

@dataclass
class MatchResult:
    property_id: UUID | None
    score: float | None
    auto_linked: bool
    suggestions: list[Suggestion]

async def suggest(conn, building_name: str | None) -> MatchResult:
    if not building_name:
        return MatchResult(None, None, False, [])

    # 1. Exact match (case + whitespace normalised) — auto-link if exactly one.
    exact = await conn.fetch(
        """
        select id, entity_id, name
        from property
        where deleted_at is null
          and lower(trim(name)) = lower(trim($1))
        """,
        building_name,
    )
    if len(exact) == 1:
        return MatchResult(exact[0]["id"], 1.0, True, [])

    # 2. Multiple exact matches → suggest all, no auto-link.
    if len(exact) > 1:
        sugs = [Suggestion(id=r["id"], score=1.0, name=r["name"]) for r in exact]
        return MatchResult(None, None, False, sugs)

    # 3. Fuzzy via pg_trgm.
    fuzzy = await conn.fetch(
        """
        select id, entity_id, name, similarity(name, $1) as score
        from property
        where deleted_at is null
          and similarity(name, $1) >= $2
        order by score desc
        limit $3
        """,
        building_name, SIMILARITY_THRESHOLD, MAX_SUGGESTIONS,
    )
    sugs = [Suggestion(id=r["id"], score=float(r["score"]), name=r["name"]) for r in fuzzy]
    return MatchResult(None, None, False, sugs)
```

Single-tenant scope: matcher searches all properties; reviewer sees the entity in the suggestion display.

### 8.6 Storage wrapper

```python
class StorageClient:
    BUCKET = "imports"
    SIGNED_URL_TTL_SECONDS = 300

    async def upload(self, batch_id: UUID, filename: str, data: bytes) -> str: ...
    async def download(self, path: str) -> bytes: ...
    async def signed_url(self, path: str) -> str: ...
    async def delete_prefix(self, batch_id: UUID) -> None: ...
```

Configuration via existing env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`). One module-level singleton, instantiated at app startup.

### 8.7 Failure-mode catalogue (parse stage)

| Failure | Behaviour |
|---|---|
| Storage download fails (transient network) | `parse_status='error'`, `errors=[{code:'storage_unavailable'}]`. Reviewer cancels + re-uploads. |
| `excel.parse` raises `HardParseError` | `parse_status='error'`, structured error from exception. |
| `engine.calculate` raises `ValueError` | `parse_status='error'`, `errors=[{code:'engine_validation_error'}]`. |
| Any other exception | `parse_status='error'`, `errors=[{code:'unrecoverable_parse_error'}]`; full stack in Sentry. |
| Worker process dies mid-batch (Render redeploy) | Items not yet processed remain placeholder; `batch.status` stuck at `parsing`. v1 surfaces a UI hint after 5 minutes; reviewer cancels + re-uploads. (No automatic retry; out of scope.) |

### 8.8 Logging

Structured JSON via Plan 2's `logging.py`. Per item: `parse_worker_item_processed` event with `{batch_id, item_id, filename, parse_status, n_warnings, n_errors, recompute_diff_pct, match_score, duration_ms}`. Per batch: `parse_worker_batch_completed` totals.

## 9. Commit loop

### 9.1 Overall shape

```python
@dataclass
class CommitSummary:
    batch_id:    UUID
    committed:   int
    failed:      int
    skipped:     int
    failures:    list[CommitFailure]
    batch_status: str  # 'committed' or 'review'

@dataclass
class CommitFailure:
    item_id:  UUID
    filename: str
    reason:   str
    message:  str

async def commit_batch(pool: asyncpg.Pool, batch_id: UUID, actor: AppUser) -> CommitSummary:
    summary = CommitSummary(batch_id, 0, 0, 0, [], "review")

    items = await import_item_q.list_for_commit(pool, batch_id)
    # rows where resolution IN ('accepted','edited') AND resolved_snapshot_id IS NULL

    for item in items:
        try:
            await _commit_one(pool, batch_id, item, actor)
            summary.committed += 1
        except CommitFailure as f:
            summary.failed += 1
            summary.failures.append(f)

    summary.skipped = await import_item_q.count_already_committed(pool, batch_id)

    if await import_item_q.all_items_terminal(pool, batch_id):
        await import_batch_q.set_status(pool, batch_id, "committed")
        await storage.delete_prefix(batch_id)
        summary.batch_status = "committed"

    await audit.log(pool, actor=actor, action="import_batch.commit",
                    target_table="import_batch", target_id=batch_id,
                    after_json=summary._to_audit_dict())
    return summary
```

### 9.2 Per-item commit

One transaction per item (Q7). Reuses Plan 2's `snapshot_q.create_with_supersede` — same code path as the manual `POST /properties/{id}/snapshots` endpoint.

```python
async def _commit_one(pool, batch_id, item, actor) -> None:
    inputs = item.resolved_inputs_json or item.parsed_inputs_json
    if not inputs:
        raise CommitFailure(item.id, item.filename, "no_inputs", "No inputs to commit")
    if not item.resolved_property_id:
        raise CommitFailure(item.id, item.filename, "no_property_link",
                            "Reviewer did not link a property")

    try:
        result = engine.calculate(ValuationInput.model_validate(inputs))
    except ValueError as e:
        raise CommitFailure(item.id, item.filename, "engine_validation_error", str(e))

    async with pool.acquire(timeout=10) as conn, conn.transaction():
        prop = await property_q.get_for_update(conn, item.resolved_property_id)
        if not prop:
            raise CommitFailure(item.id, item.filename, "property_missing",
                                "Linked property no longer exists")

        snapshot_id = await snapshot_q.create_with_supersede(
            conn,
            property_id=prop.id,
            inputs_json=inputs,
            result_json=result.model_dump(),
            engine_version=engine.__version__,
            source="excel_import",
            source_file=item.filename,
            created_by=actor.id,
        )

        await audit_q.insert(
            conn, actor_id=actor.id, actor_email=actor.email,
            action="valuation_snapshot.create",
            target_table="valuation_snapshot", target_id=snapshot_id,
            after_json={"property_id": str(prop.id),
                        "valuation_date": str(inputs["valuation_date"]),
                        "market_value": str(result.market_value),
                        "source": "excel_import",
                        "source_file": item.filename,
                        "import_item_id": str(item.id)},
        )

        await import_item_q.mark_committed(
            conn, item.id, snapshot_id=snapshot_id, actor_id=actor.id,
        )

        await audit_q.insert(
            conn, actor_id=actor.id, actor_email=actor.email,
            action="import_item.update",
            target_table="import_item", target_id=item.id,
            before_json={"resolution": item.resolution, "resolved_snapshot_id": None},
            after_json={"resolution": "committed", "resolved_snapshot_id": str(snapshot_id)},
        )
```

Invariants:
- **Reuse, don't duplicate.** `snapshot_q.create_with_supersede` is *the same function* manual entry uses. Same supersede behaviour, same `engine_version` recording, same audit pattern. Excel imports go through *exactly* the manual-entry code path; only `source` and `source_file` differ.

### 9.3 No inline entity/property creation (deviation from spec §9.6)

The original top-level spec sketched the commit loop as creating entities/properties inline. We deliberately **don't** do that here:

- **Reviewer workflow when no property exists:** UI calls `POST /entities` (if needed) and `POST /properties` (Plan 2 endpoints), then PATCHes the import item with the new `resolved_property_id`. Two extra HTTP calls per new property.
- **Backend factoring:** commit loop handles only existing-property links. PATCH endpoint accepts only an existing-id `resolved_property_id`. Zero polymorphism.
- **Audit trail unchanged:** entity/property creation is already audited by the existing endpoints.

For a single-tenant tool where most batches are revaluations of *existing* properties, this trades a tiny amount of UI work for substantial backend simplification. If usage data later shows the new-property case is common, we can re-add inline creation.

### 9.4 Failure-mode catalogue (commit stage)

| `reason` code | When | Recovery |
|---|---|---|
| `no_inputs` | Item has neither `resolved_inputs_json` nor `parsed_inputs_json` (defence-in-depth) | Edit item to add inputs |
| `no_property_link` | `resolved_property_id IS NULL` for an `accepted`/`edited` item | PATCH with a property |
| `engine_validation_error` | `engine.calculate` raises at commit time (reviewer-edited inputs invalid) | PATCH to fix |
| `property_missing` | Linked property soft-deleted between PATCH and commit | PATCH with a different property |
| `duplicate_snapshot_for_date` | Unexpected unique-constraint violation (defence-in-depth — supersede should handle this) | Investigate, edit `valuation_date` or reject |
| `unexpected_error` | Last-resort catch (DB drop, asyncpg bug) | Re-run commit (idempotent) |

### 9.5 Cleanup on terminal batch state

A batch reaches `committed` when **every** `import_item` row is in `committed` OR `rejected`. On that transition:
1. `import_batch.status = 'committed'` (only mutation outside per-item transactions).
2. `storage.delete_prefix(batch_id)` removes all original workbooks.
3. `GET /imports/{id}/items/{iid}/source` returns 410 thereafter.

`POST /imports/{id}/cancel` does the same Storage cleanup; status goes to `cancelled` instead.

`import_batch` and `import_item` rows are **never deleted** — they are the audit trail for snapshot provenance.

## 10. Exports (PDF + XLSX)

### 10.1 XLSX endpoint

One screen of code:

```python
@router.get("/snapshots/{snapshot_id}/export.xlsx")
async def get_snapshot_xlsx(
    snapshot_id: UUID,
    request: Request,
    user: AppUser = Depends(current_user),
) -> Response:
    snapshot = await snapshot_q.get(request.app.state.pool, snapshot_id)
    if not snapshot:
        raise NotFound("snapshot")

    etag = f'"{snapshot.id}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    inputs = ValuationInput.model_validate(snapshot.inputs_json)
    result = ValuationResult.model_validate(snapshot.result_json)
    workbook_bytes = engine.excel.render(inputs, result)

    return Response(
        content=workbook_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{_safe_filename(snapshot, "xlsx")}"',
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
        },
    )
```

### 10.2 PDF — file layout

```
services/exports.py        # render_snapshot_pdf(snapshot, branding) -> bytes
exports/pdf_template.html  # Jinja2, single self-contained page
exports/pdf_styles.css     # @page A4, monospace numbers
```

### 10.3 PDF page content (Q9 — option B)

**Header (every page):** firm logo (left, ~30mm wide) + firm name + firm address + firm contact line (right). Horizontal rule.

**Title block:**
- "Property Valuation Report"
- Big bold market value (R-formatted, two decimals).
- Entity → property name → property address (right-aligned).
- "Valuation date: <yyyy-mm-dd>" (left).
- "Prepared by: <created_by display name or email>" (left).

**Tenants table.** Columns: `Tenant | Description | Annual escalation | Lease period | Lease expiry | Rentable area (m²) | R/m²/pm | Gross monthly rent`. One row per resolved tenant from `result.tenants_resolved` — so the **escalated effective rent** shows, not lease base rent. Sub-total row: total area, total monthly rent. Row shading alternates.

**Parking table** (omitted if empty): `Type | Bays | R/bay/pm | Gross monthly rent`. Sub-total row.

**Income & expense block:**
```
Gross monthly income          R x,xxx,xxx.xx
Gross annual income           R x,xxx,xxx.xx

Annual operating expenses     R x,xxx,xxx.xx    (R/m²/pm | % of GAI)
Vacancy allowance             R (xxx,xxx.xx)    (xx.xx%)
Annual net income             R x,xxx,xxx.xx

Capitalisation rate                    xx.xx%
Capitalised value             R x,xxx,xxx.xx
Open market assessment        R x,xxx,xxx.xx    (rounded per snapshot.rounding policy)
```

**Notes & warnings footer.** Engine warnings list, one per line (`<icon> <code>: <message>`). If empty, italic "No warnings raised by the engine."

**Provenance footer (every page, fine print):** `Snapshot ID: <uuid> · Engine version: <semver> · Generated at: <iso8601 UTC> · Source: manual` or `Source: Excel import — <original filename>`.

Most snapshots fit one page. Many-tenant snapshots (>~25) overflow to a second page; CSS `@page` + `page-break-inside: avoid` on tables prevents mid-row breaks.

### 10.4 Template factoring

Single `pdf_template.html`, no inheritance/includes. Receives a context dict assembled in `services/exports.py::_build_context(snapshot, branding)`. **All formatting happens in the context builder, not in the template.** Template just substitutes pre-formatted strings — the boundary that lets us unit-test content without a WeasyPrint binary.

Context shape:

```python
context = {
    "branding": {
        "firm_name": str,
        "firm_logo_path": str | None,
        "firm_address_lines": list[str],
        "firm_contact_lines": list[str],
    },
    "entity": {"name": str},
    "property": {"name": str, "address": str},
    "snapshot": {
        "id": str,
        "valuation_date": str,                # "15 March 2026"
        "created_by": str,
        "engine_version": str,
        "source": str,                        # "Manual entry" | "Excel import — <filename>"
        "generated_at": str,
        "market_value_formatted": str,        # "R 12,500,000"
    },
    "tenants_resolved": list[dict],           # pre-formatted
    "parking": list[dict],
    "totals": {
        "gross_monthly_income": str,
        "gross_annual_income": str,
        "annual_operating_expenses": str,
        "opex_per_m2_pm": str,
        "opex_pct_of_gai": str,
        "vacancy_allowance_amount": str,
        "vacancy_pct": str,
        "annual_net_income": str,
        "cap_rate_pct": str,
        "capitalised_value": str,
        "market_value": str,
    },
    "warnings": list[{"code": str, "message": str, "field_path": str | None}],
}
```

### 10.5 PDF endpoint

```python
@router.get("/snapshots/{snapshot_id}/export.pdf")
async def get_snapshot_pdf(
    snapshot_id: UUID,
    request: Request,
    user: AppUser = Depends(current_user),
) -> Response:
    snapshot = await snapshot_q.get(request.app.state.pool, snapshot_id)
    if not snapshot:
        raise NotFound("snapshot")

    etag = f'"{snapshot.id}"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304)

    pdf_bytes = await run_in_threadpool(
        exports_svc.render_snapshot_pdf, snapshot, request.app.state.branding,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{_safe_filename(snapshot, "pdf")}"',
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": etag,
        },
    )
```

`run_in_threadpool` because WeasyPrint is sync CPU-bound — running it directly on the event loop would block other requests for 100–300ms.

### 10.6 Branding source — env vars in v1

| Env var | Default | Notes |
|---|---|---|
| `BRANDING_FIRM_NAME` | (required) | "Anchor Point Risk (Pty) Ltd" |
| `BRANDING_FIRM_ADDRESS_LINES` | "" | pipe-separated lines |
| `BRANDING_FIRM_CONTACT_LINES` | "" | pipe-separated lines |
| `BRANDING_FIRM_LOGO_PATH` | `branding/anchorpoint_logo.png` | absolute or repo-relative; missing file → render firm name larger instead, no broken-image |

Loaded once at app startup into `app.state.branding`.

`packages/api/branding/anchorpoint_logo.png` ships with the repo as a placeholder; user can swap.

### 10.7 Filename helper

```python
def _safe_filename(snapshot, ext: str) -> str:
    parts = [snapshot.entity.name, snapshot.property.name, snapshot.valuation_date.isoformat()]
    safe = "_".join(_slugify_for_disposition(p) for p in parts)
    return f"{safe}.{ext}"
```

`_slugify_for_disposition` strips Windows/macOS/Linux-illegal chars (`<>:"/\\|?*`), collapses whitespace, trims to 200 chars. RFC 5987 `filename*=UTF-8''...` if non-ASCII survives.

### 10.8 Render dependencies

Added to `packages/api/pyproject.toml`:

```toml
dependencies = [
  # ... existing ...
  "weasyprint>=62.0",
  "jinja2>=3.1",          # transitive via fastapi but pin explicit
]
```

Plus the apt-install in Render's build command (§11).

### 10.9 Deliberately not included

- Cover page, methodology, sign-off block (deferred to a future Plan 5 styling pass).
- Multi-page table of contents.
- Charts in the PDF (year-over-year is portfolio-dashboard / Plan 4).
- PDF signing / certification.
- Bulk export endpoint (one snapshot per request).

## 11. Deploy, CI, packaging

### 11.1 Render — `render.yaml` changes

- **Build command** prefix: `apt-get update && apt-get install -y --no-install-recommends libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libcairo2 libgdk-pixbuf-2.0-0 fonts-liberation && ...existing build command`.
- **Disk:** none.
- **New env vars:**

| Key | Default | Purpose |
|---|---|---|
| `BRANDING_FIRM_NAME` | (required) | PDF header |
| `BRANDING_FIRM_ADDRESS_LINES` | "" | PDF header |
| `BRANDING_FIRM_CONTACT_LINES` | "" | PDF header |
| `BRANDING_FIRM_LOGO_PATH` | `branding/anchorpoint_logo.png` | PDF header |
| `IMPORT_MAX_FILE_BYTES` | `10485760` (10 MB) | per-file upload cap |
| `IMPORT_PARSE_WORKER_TIMEOUT_S` | `120` | per-item ceiling, prevents zombie batches |
| `STORAGE_SIGNED_URL_TTL_S` | `300` | source-download URL TTL |

Existing Plan 2 env vars unchanged. Storage credentials reuse the existing `SUPABASE_SERVICE_ROLE_KEY`. Zero new secrets.

### 11.2 Dockerfile (future fallback)

`packages/api/Dockerfile` updated to install the same apt packages — not for deployment in v1 (we use Render's Python runtime per Q8-A) but to keep Docker as a working drop-in if we later switch.

### 11.3 Branding asset in-repo

```
packages/api/branding/
├── README.md                          # how to swap the logo
└── anchorpoint_logo.png               # placeholder; user can swap
```

Copied into the Render filesystem via the existing `pip install -e .` path.

### 11.4 GitHub Actions — `api.yml` changes

- WeasyPrint apt-install step before `pip install`.
- `pg_trgm` extension via the new migration (CI uses Supabase CLI; extension is available).
- Storage smoke against the local Supabase Storage stack (CLI-shipped).
- No Python version matrix change in this plan (Plan 2 carry-over note flagged 3.12 as optional; deferring).

### 11.5 Carry-overs from Plan 2 (folded in per Q2.1)

These land as the **first three commits** on the branch, before any Plan 3 work, so the diff stays reviewable:

1. **`packages/api/src/api/db.py`** — add `acquisition_timeout=10` to every `pool.acquire()` call site (3 sites). Test: a unit test that mocks `asyncpg.Pool.acquire` and asserts the timeout kwarg.
2. **`packages/api/src/api/errors.py`** — narrow the global `ValueError → 422` handler so it only fires inside scoped engine wrappers (`/calculate` and the new commit/parse paths). Implementation: replace global handler with a router-level dependency wrapping engine calls; remove the global. Update `tests/unit/test_errors.py`.
3. **`packages/api/pyproject.toml` + `_version.py`** — bump `0.1.0 → 0.2.0` (semver minor; additive features incoming).

### 11.6 What stays the same

| Area | Status |
|---|---|
| Render service (web service, Python runtime, region) | Unchanged |
| Existing env vars from Plan 2 | Unchanged |
| GitHub Actions runner (Ubuntu) | Unchanged |
| Supabase CLI version pinned in CI | Unchanged |
| `packages/api/scripts/smoke.sh` | **Extended** — adds curl checks for `/imports`, `/snapshots/{id}/export.pdf`, `/snapshots/{id}/export.xlsx` against a seeded snapshot |

### 11.7 Operator runbook (`packages/api/README.md` addition)

1. Merge `plan-3-imports-exports` to `main`.
2. Render auto-deploy triggers (existing webhook). Build runs apt-install + pip install. ~3-4 min build, up from ~1.5 min in Plan 2.
3. Apply migrations: `supabase db push --db-url <prod-url>` (manual one-shot, same as Plan 2).
4. Set `BRANDING_*` env vars in Render dashboard (or via `render.yaml` literals).
5. Smoke: `packages/api/scripts/smoke.sh <PROD_URL> <JWT>`.
6. Verify in Swagger UI: POST a test workbook to `/imports`, confirm 202 + parse, PATCH commit, confirm snapshot lands.

No downtime expected — additive endpoints, additive tables.

### 11.8 Rollback plan

1. Render dashboard → roll back to previous deploy (one click). Removes all Plan 3 endpoints and code.
2. Migrations are *additive only* — leaving them in place during rollback is safe.
3. The `imports` Storage bucket and any `import_batch`/`import_item` rows are orphaned but harmless.

The carry-over to `errors.py` is the only change touching Plan 2 code paths. Risk: a `ValueError` raised somewhere we didn't anticipate now produces a generic 500 instead of 422. Mitigation: integration sweep covers all Plan 2 endpoints in CI.

## 12. Testing strategy

### 12.1 Test layers

| Layer | Marker | Runs in | Coverage in Plan 3 |
|---|---|---|---|
| Unit (no DB, no Storage, no WeasyPrint) | (default) | every CI run | schemas, validators, formatters, matcher SQL composition (mocked), commit-loop control flow (mocked DB), context builder for PDF, error envelope shapes |
| Integration (real DB + Storage) | `@pytest.mark.integration` | every CI run with `supabase start` | every router end-to-end, parse-worker against real `.xlsx`, commit loop against real DB, RLS sanity, Storage round-trips |
| PDF visual (real WeasyPrint) | `@pytest.mark.pdf` | local + CI when apt deps present | `render_snapshot_pdf` produces a valid PDF; pikepdf-based content checks (not pixel diff) |

### 12.2 New test files

```
packages/api/tests/
├── unit/
│   ├── test_carryover_db_timeout.py
│   ├── test_carryover_errors_narrowing.py
│   ├── test_imports_schemas.py
│   ├── test_matcher_query.py
│   ├── test_parse_worker_per_item.py
│   ├── test_commit_worker.py
│   ├── test_exports_context_builder.py
│   └── test_exports_filename.py
├── integration/
│   ├── test_imports_upload.py
│   ├── test_imports_list_detail.py
│   ├── test_imports_patch.py
│   ├── test_imports_cancel.py
│   ├── test_imports_commit.py
│   ├── test_imports_source_redirect.py
│   ├── test_imports_rls.py
│   ├── test_imports_storage_cleanup.py
│   ├── test_exports_pdf_endpoint.py
│   └── test_exports_xlsx_endpoint.py
└── pdf/                              # NEW directory
    ├── conftest.py
    ├── reference/
    │   └── canonical_one_pager.pdf
    └── test_pdf_visual.py
```

### 12.3 Sample workbook fixtures

```
packages/api/tests/fixtures/imports/
├── canonical.xlsx
├── canonical_no_parking.xlsx
├── canonical_multi_sheet.xlsx
├── label_drift_minor.xlsx           # → parse_status=error per Q3-A
├── missing_tenants.xlsx
├── recompute_mismatch.xlsx
├── exact_name_match.xlsx
├── fuzzy_name_match.xlsx
└── corrupt.xlsx
```

Synthetic, no real client data. ~9 small files (~10–20 KB each). Generated by `tests/fixtures/imports/build.py` from Python dicts via `valuation_engine.excel.render`; committed as binaries.

### 12.4 Storage in tests

The Supabase CLI ships Storage. Integration `conftest.py`:
- Resets the `imports` bucket before each test.
- Provides a `storage_client` fixture pointing at the local stack.
- Asserts bucket cleanup at the end of `test_imports_storage_cleanup.py`.

No Storage mocking — Plan 2 already learned the asyncpg-jsonb-codec lesson about mocked vs real interactions.

### 12.5 PDF visual tests

We don't pixel-diff (fragile across Pango versions). We assert:

1. **Validity** via `pikepdf.Pdf.open(bytes_io)` — succeeds.
2. **Page count** matches expectation (1 for the canonical one-pager, 2 for a 30-tenant snapshot).
3. **Text content** via `pikepdf.extract_text` — contains every expected string (entity name, property name, formatted market value, every warning message, snapshot ID, engine version).
4. **Size sanity** — within ±20% of a reference (~50 KB). Catches "logo embedded as 5 MB raw bitmap" bugs.

`pikepdf` added to `[tool.uv]dev-dependencies`. Production doesn't need it.

### 12.6 Carry-over tests (folded in)

- **`test_carryover_db_timeout.py`** — patches `asyncpg.Pool.acquire`, asserts every call site passes `timeout=10`. Greps the codebase at test time to catch new unprotected sites — small enforcement test.
- **`test_carryover_errors_narrowing.py`** — verifies:
  - `ValueError` inside the engine wrapper → 422 `engine_validation_error`. ✓
  - `ValueError` outside → 500 generic `internal_error`. ✓ (intentional change from previous global handler.)

### 12.7 Coverage targets (soft, not enforced)

- All routers: 100% line on happy paths + every documented status code.
- `services/parse_worker.py`, `services/commit_worker.py`: ≥90% line.
- `services/matcher.py`: ≥95% line (every branch in `suggest`).
- `services/exports.py::_build_context`: 100% line — pure function.
- `services/storage.py`: ≥80% line (integration coverage carries the rest).

### 12.8 Deliberately not tested

- Render's apt-install step (covered by post-deploy smoke).
- Performance / load.
- Cross-Pango-version PDF rendering (CI pins one version).
- The 130 real client workbooks (engine-side coverage in Plan 1; Plan 3 uses synthetic fixtures only to keep CI free of client data).

### 12.9 Local dev workflow (`packages/api/README.md` addition)

```bash
# Fast loop — no Docker
cd packages/api
uv run pytest -m "not integration and not pdf"   # ~3 seconds, no setup

# Full local — needs Docker for Supabase CLI
supabase start                                    # repo root
cd packages/api
export DATABASE_URL=postgresql://postgres:postgres@localhost:54322/postgres
export SUPABASE_URL=http://localhost:54321
export SUPABASE_SERVICE_ROLE_KEY=<from `supabase status`>
export SUPABASE_JWT_SECRET=<from `supabase status`>
uv run pytest                                     # all marks; ~30 seconds
```

## 13. Open items deferred to later versions

- Inline entity/property creation inside the commit endpoint.
- Aggressive parser recovery for non-canonical layouts.
- Pixel-fidelity branded report cover pages and methodology copy.
- Bulk PDF/XLSX export (zip).
- Storage-side caching of rendered exports.
- Cross-batch concurrent-commit advisory locking.
- `last_heartbeat_at` + sweeper for batches stuck in `parsing` after worker crashes.
- Python 3.12 CI matrix (carry-over deferred).
- Web UI (Plan 4).
